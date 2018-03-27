#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk
import os
import uuid
import math
import subprocess
import hyperspeed.afterscript
threading = hyperspeed.afterscript.threading
gobject = hyperspeed.afterscript.gobject

title          = 'HF Delivery'

class TagReader(object):

    def __init__(self, afterscript):
        afterscript.onRenderChangeCallbacks.append(self.onRenderChange)
    def onRenderChange(self, afterscript):
        render = afterscript.render
        if render == None:
            return
        inpixels = render.resX * render.resY

        # Default values
        pixels = 1280*720
        upload = True
        master = False
        crf = '20'
        minrate = '0'
        maxrate = '4M'
        bufsize = '15M'
        ext = '.mp4'
        aac = True
        pix_fmt = "yuv420p"
        nobug = True
        noslate = False
        linkSuffix = ''
        link = False

        #print repr(render.tags)
        # User overrides
        if 'noupload' in render.tags:
            upload = False
        if 'nobug' in render.tags:
            nobug = True
        if 'noslate' in render.tags:
            noslate = True
        if '360p' in render.tags or 'lowres'in render.tags or 'lr'in render.tags:
            pixels = 640*360
            maxrate = '1M'
            bufsize = '4M'
        if 'master'in render.tags or '1080p' in render.tags or 'highres'in render.tags or 'hr'in render.tags:
            pixels = 2048*1152
            crf = '18'
            minrate = '5M'
            maxrate = '18M'
            bufsize = '36M'
            master = True
            nobug = True
            noslate = True
        if 'mov' in render.tags:
            ext = '.mov'
            upload = False
        if 'pcm' in render.tags:
            aac = False
            ext = '.mov'
            upload = False
        if '422' in render.tags:
            pix_fmt = "yuv422p"
        for tag in render.tags:
            if tag.startswith('crf') and tag[3:].isdigit():
                crf = tag[3:]
            elif tag.startswith('minrate') and tag[7:].isdigit():
                minrate = tag[7:]
            elif tag.startswith('maxrate') and tag[7:].isdigit():
                maxrate = tag[7:]
            elif tag.startswith('link.'):
                linkSuffix = '.'+tag[5:]
            elif tag.startswith('link'):
                linkSuffix = '.'+tag[4:]
            elif tag.startswith('res') and tag[4].isdigit():
                newpixels = tag[3:]
                if newpixels.isdigit():
                    pixels = int(newpixels)
                elif '*' in newpixels:
                    newres = newpixels.split('*')
                    if newres[0].isdigit() and newres[1].isdigit():
                        pixels = int(newres[0])*int(newres[1])
            
        scale = math.sqrt(float(pixels)/float(inpixels))
        width = min(int(round(float(render.resX)*scale*0.25)*4.0), render.resX)
        scale = float(width)/float(render.resX)
        height = min(int(round(float(render.resY)*scale*0.25)*4.0), render.resY)

        if aac:
            acodec = ' aac '
        else:
            acodec = ' pcm_s24le '

        cmd            = "-vsync 0 -movflags faststart -crf "+crf+" -minrate "+minrate+" -maxrate "+maxrate+" -bufsize "+bufsize+" -filter_complex 'scale="+"%i:%i" % (width, height) +":out_color_matrix=bt709,setsar=1' -pix_fmt yuv420p -c:v libx264 -c:a "+acodec+" -b:a 160k -strict -2 -ac 2 -ar 44100 -af pan=stereo:c0=c0:c1=c1"
        afterscript.cmd = [cmd]
        afterscript.cmd_update()
        gobject.idle_add(afterscript.uploader.automatically.set_active, upload)
# Path relative to primary output folder of render:P
# default_output = '[project]_[render_name].[codec].mov'
# Absolute path:
default_output = '/Volumes/SAN3/Masters/[project]/[project]_[rendername]/[project]_[rendername].h264.mp4'

class RestUploader(object):
    ready = False
    def __init__(self, afterscript):
        afterscript.uploader = self
        self.afterscript = afterscript
        if not 'rest_endpoint' in afterscript.settings:
            afterscript.settings['rest_endpoint'] = ''
        gobject.idle_add(self.initGUI)
    def initGUI(self):
        afterscript = self.afterscript
        expander = gtk.Expander('Upload settings')
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        label =  gtk.Label('Upload address:')
        hbox.pack_start(label, False, False, 5)
        entry = gtk.Entry()
        entry.set_text(afterscript.settings['rest_endpoint'])
        entry.connect('changed', afterscript.on_settings_change, 'rest_endpoint')
        hbox.pack_start(entry)
        label = self.hostStatusLabel = gtk.Label('')
        hbox.pack_start(label, False, False, 5)
        hbox.show_all()
        vbox.pack_start(hbox, False, False, 5)
        hbox = gtk.HBox()
        label =  gtk.Label('Authentication token:')
        hbox.pack_start(label, False, False, 5)
        entry = self.tokenEntry = gtk.Entry()
        entry.connect('changed', afterscript.on_settings_change, 'rest_token')
        hbox.pack_start(entry)
        label = self.tokenStatusLabel = gtk.Label('')
        hbox.pack_start(label, False, False, 5)
        hbox.show_all()
        vbox.pack_start(hbox, False, False, 5)
        expander.add(vbox)
        vbox = gtk.VBox()
        vbox.pack_start(expander, False, False, 5)
        checkbox = self.automatically = gtk.CheckButton('Upload automatically')
        checkbox.set_active(True)
        vbox.pack_start(checkbox, False, False, 5)
        hbox = self.uploadHbox = gtk.HBox()
        hbox.set_no_show_all(True)
        button =  gtk.Button('Upload')
        button.connect("clicked", self.upload)
        hbox.pack_start(button, False, False, 5)
        progressbar = self.progressbar = gtk.ProgressBar()
        progressbar.set_text("Upload has not started")
        hbox.pack_start(progressbar)
        vbox.pack_start(hbox, False, False, 5)
        hbox = self.linkBox = gtk.HBox()
        hbox.set_no_show_all(True)
        label =  gtk.Label('URL:')
        hbox.pack_start(label, False, False, 5)
        link = self.link =  gtk.LinkButton('', '')
        hbox.pack_start(link, False, False, 5)
        vbox.pack_start(hbox, False, False, 5)
        vbox.show_all()
        afterscript.window.get_children()[0].pack_start(vbox, False, False)
        afterscript.onRenderChangeCallbacks.append(self.onRenderChange)
        afterscript.onAfterscriptStartCallbacks.append(self.onAfterscriptStart)
        afterscript.onSuccessCallbacks.append(self.onAfterscriptSuccess)
        if not afterscript.settings['rest_endpoint'].startswith('http'):
            hostStatusLabel.set_markup('<span color="#aa4400">Please enter a valid url</span>')
        else:
            self.onRenderChange(afterscript)
    def onAfterscriptStart(self, afterscript):
        gobject.idle_add(self.uploadHbox.hide)
    def onAfterscriptSuccess(self, afterscript):
        if not self.ready:
            return
        gobject.idle_add(self.uploadHbox.set_no_show_all, False)
        gobject.idle_add(self.uploadHbox.show_all)
        if self.automatically.get_active():
            t = threading.Thread(target=self.upload, name='Upload')
            t.setDaemon(True)
            t.start()
    def upload(self, widget=False):
        afterscript = self.afterscript
        if not self.ready:
            return
        CHUNK_SIZE = 4*1000*1000
        file_size = os.path.getsize(afterscript.output_path)
        chunk_dir = '/tmp/upload-chunks/'
        if not os.path.isdir(chunk_dir):
            try:
                os.makedirs(chunk_dir)
            except OSError:
                print 'Could not create chunks temp dir: %s' % chunk_dir
                return;
        chunk_path = os.path.join(chunk_dir, os.path.basename(afterscript.output_path))
        dzuuid = uuid.uuid4()
        dztotalchunkcount = math.ceil(file_size / float(CHUNK_SIZE))
        chunk_start = 0
        dzchunkindex = -1
        with open(afterscript.output_path, 'rb') as f:
            while chunk_start < file_size:
                dzchunkindex += 1
                chunk_end = chunk_start + CHUNK_SIZE
                open(chunk_path, 'wb').write(f.read(CHUNK_SIZE))
                chunk_end = min(chunk_end, file_size)
                cmd = ['curl', '-v', '-H', 'Cookie: token=%s' % afterscript.settings['rest_token'], '-H', 'Project: %s' % afterscript.render.project, afterscript.settings['rest_endpoint']]
                #cmd += ['-X', 'POST', '-d', '@%s' % afterscript.output_path]
                #cmd += ['-H', 'Transfer-Encoding: chunked']
                #cmd += ['-X', 'POST']
                cmd += ['-F', 'dzuuid=%s' % dzuuid]
                cmd += ['-F', 'dztotalchunkcount=%i' % dztotalchunkcount]
                cmd += ['-F', 'dzchunkindex=%s' % dzchunkindex]
                #cmd += ['-T', '-']
                cmd += ['-F', 'file=@%s' % chunk_path]
                response, status = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                if '< HTTP/1.1 4' in status:
                    gobject.idle_add(self.progressbar.set_text, 'Upload failed')
                    return
                chunk_start = chunk_end
                progress_float = chunk_end/float(file_size)
                progress_percent = progress_float * 100.0
                progress_string = '%5.2f%%' % progress_percent
                gobject.idle_add(self.progressbar.set_text, progress_string)
                gobject.idle_add(self.progressbar.set_fraction, progress_float)
        gobject.idle_add(self.progressbar.set_fraction, 1)
        gobject.idle_add(self.progressbar.set_text, 'Upload complete')
        os.remove(chunk_path)

        cmd = ['curl', '-v', '-H', 'Cookie: token=%s' % afterscript.settings['rest_token'], '-H', 'Project: %s' % afterscript.render.project, afterscript.settings['rest_endpoint']]
        #cmd += ['-X', 'POST', '-d', '@%s' % afterscript.output_path]
        cmd += ['-F', 'file=@%s' % afterscript.output_path]

    def onRenderChange(self, afterscript):
        if afterscript.render == None:
            return
        self.ready = False
        if afterscript.settings['rest_endpoint'].startswith('http'):
            cmd = ['curl', '-v', '-H', 'Cookie: token=%s' % afterscript.settings['rest_token'], '-H', 'Project: %s' % afterscript.render.project, afterscript.settings['rest_endpoint']]
            #print ' '.join(cmd)
            response, status = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
            if '< HTTP/1.1 200 OK' in status:
                url = response
                gobject.idle_add(self.tokenStatusLabel.set_markup, '<b>OK</b>')
                gobject.idle_add(self.tokenEntry.hide)
                gobject.idle_add(self.link.set_label, url)
                gobject.idle_add(self.link.set_uri, url)
                gobject.idle_add(self.linkBox.set_no_show_all, False)
                gobject.idle_add(self.linkBox.show_all)
                self.ready = True
            else:
                gobject.idle_add(self.tokenStatusLabel.set_markup, '<span color="#aa4400">Please enter a valid token</span>')

def onInit(afterscript):
    RestUploader(afterscript)
    TagReader(afterscript)

cmd = ''
hyperspeed.afterscript.AfterscriptFfmpeg(__file__, cmd, default_output, title, onInitCallback=onInit)
hyperspeed.afterscript.gtk.main()
