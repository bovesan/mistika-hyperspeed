#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk
import subprocess
import hyperspeed.afterscript
gobject = hyperspeed.afterscript.gobject

title          = 'HF Delivery'
cmd            = '-vsync 0 -movflags faststart -crf 20 -minrate 0 -maxrate 4M -bufsize 15M -filter_complex "scale=1280:720:out_color_matrix=bt709,setsar=1" -pix_fmt yuv420p -vcodec libx264 -c:a aac -b:a 160k -strict -2 -ac 2 -ar 44100 -acodec aac -af pan=stereo:c0=c0:c1=c1'
# Path relative to primary output folder of render:P
# default_output = '[project]_[render_name].[codec].mov'
# Absolute path:
default_output = '/Volumes/SAN3/Masters/[project]/[project]_[rendername]/[project]_[rendername].h264.mp4'

class Uploader(object):
    ready = False
    def __init__(self, afterscript):
        afterscript.upload = self
        self.afterscript = afterscript
        if not 'rest_endpoint' in afterscript.settings:
            afterscript.settings['rest_endpoint'] = ''
        gobject.idle_add(self.initGUI)
        afterscript.onRenderChangeCallbacks.append(self.onRenderChange)
        afterscript.onSuccessCallbacks.append(self.onAfterscriptSuccess)
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
        hbox = gtk.HBox()
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
        if not afterscript.settings['rest_endpoint'].startswith('http'):
            hostStatusLabel.set_markup('<span color="#aa4400">Please enter a valid url</span>')
        else:
            self.onRenderChange(afterscript)
    def onAfterscriptSuccess(self, afterscript):
        if not self.ready:
            return
        self.upload()
    def upload(self, widget=False):
        afterscript = self.afterscript
        if not self.ready:
            return
        cmd = ['curl', '-v', '-H', 'Cookie: token=%s' % afterscript.settings['rest_token'], '-H', 'Project: %s' % afterscript.render.project, afterscript.settings['rest_endpoint']]
        #cmd += ['-X', 'POST', '-d', '@%s' % afterscript.output_path]
        cmd += ['-F', 'file=@%s' % afterscript.output_path]
        response, status = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        if '< HTTP/1.1 200 OK' in status:
            gobject.idle_add(self.progressbar.set_fraction, 1)
            gobject.idle_add(self.progressbar.set_text, 'Upload complete')

    def onRenderChange(self, afterscript):
        self.ready = False
        if afterscript.settings['rest_endpoint'].startswith('http'):
            cmd = ['curl', '-v', '-H', 'Cookie: token=%s' % afterscript.settings['rest_token'], '-H', 'Project: %s' % afterscript.render.project, afterscript.settings['rest_endpoint']]
            print ' '.join(cmd)
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

hyperspeed.afterscript.AfterscriptFfmpeg(__file__, cmd, default_output, title, onInitCallback=Uploader)
hyperspeed.afterscript.gtk.main()
