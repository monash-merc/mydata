"""
Memcached

http://memcached.org/

"""
import sys
import os
import memcache
import re
import subprocess
import getpass
import psutil

from logger.Logger import logger


defaultStartupInfo = None
defaultCreationFlags = 0
if sys.platform.startswith("win"):
    defaultStartupInfo = subprocess.STARTUPINFO()
    defaultStartupInfo.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
    defaultStartupInfo.wShowWindow = subprocess.SW_HIDE
    import win32process
    defaultCreationFlags = win32process.CREATE_NO_WINDOW


class MemCacheDaemon():
    MEMCACHED_DIR = os.path.join('memcached', sys.platform)
    pid = None

    def __init__(self):
        """
        Locate the Memcached binary on various systems.
        """
        if sys.platform.startswith("win"):
            if hasattr(sys, "frozen"):
                f = lambda x: os.path.join(os.path.dirname(sys.executable),
                                           self.MEMCACHED_DIR, x)
            else:
                try:
                    mydataModulePath = \
                        os.path.dirname(pkgutil.get_loader("MyData").filename)
                except:
                    mydataModulePath = os.getcwd()
                f = lambda x: os.path.join(mydataModulePath,
                                           self.MEMCACHED_DIR, x)
            self.memcached = f("memcached.exe")
        else:
            self.memcached = "/usr/bin/memcached"

    def Start(self):
        if sys.platform.startswith("win32"):
            self.memcachedProcess = \
                subprocess.Popen([self.memcached, "-l", "127.0.0.1"],
                                 stdin=None, stdout=None,
                                 stderr=None, close_fds=True,
                                 startupinfo=defaultStartupInfo,
                                 creationflags=defaultCreationFlags
                                 | win32process.DETACHED_PROCESS)
        else:
            self.memcachedProcess = \
                subprocess.Popen("%s -l 127.0.0.1" % self.memcached,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, shell=True,
                                 universal_newlines=True,
                                 startupinfo=defaultStartupInfo,
                                 creationflags=defaultCreationFlags)
        self.pid = self.memcachedProcess.pid

    def Stop(self):
        """
        Only stop MemCache Daemon if it was started by this MyData process. 

        TO DO !!!
        """
        pass


    def GetPid(self):
        """
        Test if MemCache Daemon is already running, and if so, return its PID.
        Assume default binary name (memcached.exe or memcached)

        The TASKLIST method (for Windows) can also get the PID:

        Image Name             PID Session Name        Session#    Mem Usage
        ================= ======== ================ =========== ============
        memcached.exe         6760 Console                    1      4,792 K

        The psutil method should work on all platforms, but on Windows,
        sometimes the Image Name (memcached.exe) is missing, which is what we
        need to match on, so we're using TASKLIST instead.

        """
        username = getpass.getuser()
        if sys.platform.startswith("win"):
            proc = subprocess.Popen('TASKLIST '
                                    '/FI "USERNAME eq %s" '
                                    '/FI "IMAGENAME eq MEMCACHED.EXE"'
                                    % username,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    startupinfo=defaultStartupInfo,
                                    creationflags=defaultCreationFlags,
                                    shell=True)
            stdout, _ = proc.communicate()
            if proc.returncode != 0:
                raise Exception(stdout)

            for row in stdout.split("\n"):
                m = re.match(r"^\s*memcached.exe\s+(\d+)\s+.*$",
                             row, re.IGNORECASE)
                if m:
                    pid = m.groups()[0]
                    return int(pid)
            return None
        else:
            for p in psutil.process_iter():
                if p.name() == "memcached":
                    return int (p.pid)
            return None

    def IsRunning(self):
        return (self.GetPid() is not None)

class MemCacheClient(memcache.Client):
    """
    Adding namespace support to memcache.Client
    https://webkist.wordpress.com/2008/06/04/python-memcache-module-extension/
    """
    def __init__(self, servers=None, debug=0, namespace=None):
        super(MemCacheClient, self).__init__(servers, debug=debug)

        if namespace:
            self._namespace = namespace
        else:
            self._namespace=""

    def get_namespace(self):
        return self._namespace

    def set_namespace(self, namespace):
        self._namespace = namespace

    # GET
    def get(self, key):
        if self._namespace:
            key = self._namespace + key
        try:
            val = super(MemCacheClient, self).get(key)
        except KeyError:
            val = None
        return val

    def gets(self, key):
        if self._namespace:
            key = self._namespace + key
        return super(MemCacheClient, self).gets(key)

    def get_multi(self, keys, key_prefix=''):
        if self._namespace:
            key_prefix = self._namespace + key_prefix
        return super(MemCacheClient, self).get_multi(keys,
                                                     key_prefix=key_prefix)

    # SET
    def set(self, key, val, time=0, min_compress_len=0):
        if self._namespace:
            key = self._namespace + key
        return super(MemCacheClient, self).set(key, val, time=time,
                                       min_compress_len=min_compress_len)

    def set_multi(self, mapping, time=0, key_prefix='',
                  min_compress_len=0):
        if self._namespace:
            key_prefix = self._namespace + key_prefix
        return super(MemCacheClient, self)\
                .set_multi(mapping, time=time, key_prefix=key_prefix,
                           min_compress_len=min_compress_len)

    def cas(self, key, value, time=0, min_compress_len=0):
        if self._namespace:
            key = self._namespace + key
        return super(MemCacheClient, self).cas(key, value, time,
                                               min_compress_len)


    # DELETE
    def delete(self, key, time=0):
        if self._namespace:
            key = self._namespace + str(key)
        return super(MemCacheClient, self).delete(key, time=time)

    def delete_multi(self, keys, time=0, key_prefix=''):
        if self._namespace: key_prefix=self._namespace + key_prefix
        return super(MemCacheClient, self).delete_multi(keys, time=time,
                                                key_prefix=key_prefix)

    # EVERYTHING ELSE
    def add(self, key, val, time=0, min_compress_len=0):
        if self._namespace:
            key = self._namespace + str(key)
        super(MemCacheClient, self).add(key, val, time=time,
                                min_compress_len=min_compress_len)

    def incr(self, key, delta=1):
        if self._namespace:
            key = self._namespace + str(key)
        super(MemCacheClient, self).incr(key, delta=delta)

    def replace(self, key, val, time=0, min_compress_len=0):
        if self._namespace:
            key = self._namespace + str(key)
        super(MemCacheClient, self).replace(key, val, time=time,
                                    min_compress_len=min_compress_len)

    def decr(self, key, delta=1):
        if self._namespace:
            key = self._namespace + str(key)
        super(MemCacheClient, self).decr(key, delta=delta)
