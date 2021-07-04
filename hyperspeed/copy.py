#!/usr/bin/env python2

import os
import shutil
import time
import atexit
import re
import tempfile

def copyfileobj(fsrc, fdst, callback, length=1024 * 1024):
    try:
        # check for optimisation opportunity
        if "b" in fsrc.mode and "b" in fdst.mode and fsrc.readinto:
            return _copyfileobj_readinto(fsrc, fdst, callback, length)
    except AttributeError:
        # one or both file objects do not support a .mode or .readinto attribute
        pass

    state = { 'abort': False }
    def exitHandler():
        state['abort'] = True
    atexit.register(exitHandler)

    fsrc_read = fsrc.read
    fdst_write = fdst.write

    copied = 0
    while True:
        if state['abort']:
            break
        buf = fsrc_read(length)
        if not buf:
            break
        fdst_write(buf)
        copied += len(buf)
        callback(copied)

# differs from shutil.COPY_BUFSIZE on platforms != Windows
READINTO_BUFSIZE = 1024 * 1024

def _copyfileobj_readinto(fsrc, fdst, callback, length=0):
    """readinto()/memoryview() based variant of copyfileobj().
    *fsrc* must support readinto() method and both files must be
    open in binary mode.
    """
    fsrc_readinto = fsrc.readinto
    fdst_write = fdst.write

    if not length:
        try:
            file_size = os.stat(fsrc.fileno()).st_size
        except OSError:
            file_size = READINTO_BUFSIZE
        length = min(file_size, READINTO_BUFSIZE)

        
    state = { 'abort': False }
    def exitHandler():
        state['abort'] = True
    atexit.register(exitHandler)

    copied = 0
    with memoryview(bytearray(length)) as mv:
        while True:
            if state['abort']:
                break
            n = fsrc_readinto(mv)
            if not n:
                break
            elif n < length:
                with mv[:n] as smv:
                    fdst.write(smv)
            else:
                fdst_write(mv)
            copied += n
            callback(copied)

def dehumanizeRate(humanString):
    Bps = int(re.findall(r'\d+', humanString)[0])
    if 'b' in humanString:
        Bps *= 8
    if 'k' in humanString.lower():
        Bps *= 1024
    if 'm' in humanString.lower():
        Bps *= 1024*1024
    if 'g' in humanString.lower():
        Bps *= 1024*1024*1024
    if 't' in humanString.lower():
        Bps *= 1024*1024*1024*1024
    if 'p' in humanString.lower():
        Bps *= 1024*1024*1024*1024*1024
    return Bps

def copy_with_progress(src_path, dst_path, callback, frame_ranges=None):
    import subprocess
    # ssh-copy-id -o ProxyJump=hocus@s.hocusfocus.no mistika@mistika1
    state = {
        'bytesPrev': 0,
        'timePrev': time.time(),
    }
    src_remote = re.search(r'\S+\:.+', src_path)
    if dst_path.endswith('/'):
        dst_path+=os.path.basename(src_path)
    dst_remote = re.search(r'\S+\:.+', dst_path)
    if src_remote or dst_remote: # ssh
        cmd = ['rsync', '--progress', '-Ia', '--no-perms', '--no-owner', '--no-group', '--protect-args']
        ssharg = 'ssh '
        if src_remote:
            args = src_path.replace(src_remote.group(), '')
            src_path = src_remote.group()
            ssharg += args
            dst_dir = os.path.dirname(dst_path)
            if not os.path.exists(dst_dir):
                try:
            	    os.makedirs(dst_dir)
                except:
                    print 'Could not create directory: %s' % dst_dir
                    return false
        if dst_remote:
            args = dst_path.replace(dst_remote.group(), '')
            dst_path = dst_remote.group()
            ssharg += args
            host, destination_path_on_host = dst_path.split(':', 1)
            sshCmd = ssharg.split() + [host, 'mkdir', '-p', '"'+os.path.dirname(destination_path_on_host)+'"']
            subprocess.call(sshCmd)
        cmd += ['-e', ssharg]
        if frame_ranges:
            sequence_files = []
            basename = os.path.basename(src_path)
            for frame_range in frame_ranges:
                for frame_n in range(frame_range.start, frame_range.end+1):
                    sequence_files.append(basename % frame_n)
            sequence_length = len(sequence_files)
            frames_done = 0
            temp_handle = tempfile.NamedTemporaryFile()
            temp_handle.write('\n'.join(sequence_files) + '\n')
            temp_handle.flush()
            src_path = os.path.dirname(src_path)+'/'
            dst_path = os.path.dirname(dst_path)+'/'
            cmd += ['-vv', '--out-format="%n was copied %l"', '--files-from=%s' % temp_handle.name]
        cmd += [src_path, dst_path]
        #print cmd
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        def exitHandler():
            if proc.returncode == None:
                proc.kill()
        atexit.register(exitHandler)
        bytesCopied = 0
        progress = 0
        rate = 0
        while proc.returncode == None:
            output = ''
            char = None
            while not char in ['\r', '\n', '']:
                # proc.poll()
                # if proc.returncode != None:
                #     break
                char = proc.stdout.read(1)
                output += char
            #print output,
            fields = output.split()
            if len(fields) >= 4 and fields[1].endswith('%'):
                progress_percent = float(fields[1].strip('%'))
                bytesCopied = int(fields[0])
                progress = progress_percent / 100.0
                rate = dehumanizeRate(fields[2])
                callback(bytesCopied, progress, rate)
            else:
                match = re.match(r'was copied (\d+)$', output)
                if frame_ranges and output.strip().endswith('is uptodate') or match:
                    frames_done += 1
                    now = time.time()
                    timeDelta = now - state['timePrev']
                    if match:
                        bytesDelta = int(match.group())
                        bytesCopied += bytesDelta
                        rate = float(bytesDelta) - timeDelta
                    progress = float(frames_done) / float(sequence_length)
                    callback(bytesCopied, progress, rate)

                # callback(bytesCopied, progress, '%s (%s)' % (rate, fields[2]))
            # else:
            #     print output
            proc.poll()
        if frame_ranges:
            temp_handle.close()
        if proc.returncode == 0:
            progress = 1
        callback(bytesCopied, progress, rate)
        return proc.returncode == 0
    else:
        destination_folder = os.path.dirname(dst_path)
        if not os.path.isdir(destination_folder):
            try:
                os.makedirs(destination_folder)
            except OSError:
                print 'Could not create destination directory', destination_folder
        if frame_ranges:
            totalSize = 0
            frameSizes = {}
            for frame_range in frame_ranges:
                for frame_n in range(frame_range.start, frame_range.end+1):
                    frameSize = os.path.getsize(src_path % frame_n)
                    frameSizes[frame_n] = frameSize
                    totalSize += frameSize
        else:
            totalSize = os.path.getsize(src_path)
        def internalCallback(bytesCopied):
            progress = float(bytesCopied) / float(totalSize)
            bytesDelta = bytesCopied - state['bytesPrev']
            now = time.time()
            timeDelta = now - state['timePrev']
            rate = float(bytesDelta) / timeDelta
            state['bytesPrev'] = bytesCopied
            state['timePrev'] = now
            callback(bytesCopied, progress, rate)
        if frame_ranges:
            bytesCopied = 0
            for frame_range in frame_ranges:
                for frame_n in range(frame_range.start, frame_range.end+1):
                    if subprocess.call(['cp', '-p', src_path % frame_n, dst_path % frame_n]) == 0:
                        bytesCopied += frameSizes[frame_n]
                        internalCallback(bytesCopied)
            return bytesCopied == totalSize
        else:
            proc = subprocess.Popen(['cp', '-p', src_path, dst_path])
            first = True
            while proc.returncode == None:
                if first:
                    first = False
                else:
                    bytesCopied = 0
                    try:
                        bytesCopied = os.path.getsize(dst_path)
                    except Exception as e:
                        pass
                    internalCallback(bytesCopied)
                time.sleep(1)
                proc.poll()
            success = proc.returncode == 0
            if success:
                internalCallback(totalSize)
            return success
        # bufferSize = 100 * 1024 * 1024;
        # fsrc = open(src_path, 'rb')
        # fdst = open(dst_path, 'wb')
        # copyfileobj(fsrc, fdst, internalCallback, bufferSize)
        # shutil.copymode(src_path, dst_path)
        # shutil.copystat(src_path, dst_path)
        # return True


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print 'Usage:'
        print 'copy.py src dst'
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2]
    def callback(bytesCopied, progress, rate):
        print bytesCopied, progress * 100.0, '%', rate, 'Bps'

    copy_with_progress(src, dst, callback)
