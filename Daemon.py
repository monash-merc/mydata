import threading
from random import randint
import time
import os
import wx

import MemCache
from Util import PidIsRunning
from logger.Logger import logger


class Daemon(threading.Thread):
    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
        self.namespace = "%s_" % self.name
        memcacheClient = MemCache.MemCacheClient(['127.0.0.1:11211'],
                                                 namespace=self.namespace,
                                                 debug=0)
        memcacheDaemon = MemCache.MemCacheDaemon()
        memcacheDaemonPid = memcacheDaemon.GetPid()
        if memcacheDaemonPid:
            success = memcacheClient.set('test_key', 'test_value')
            memcacheClient.delete('test_key')
            if success:
                memcacheClient.set("daemon_pid", str(os.getpid()))
                self.namespace = "%s_%d_" % (self.name, os.getpid())
                memcacheClient.set_namespace("%s" % self.namespace)

                memcacheClient.set("clients", [])
                clients = memcacheClient.get("clients")

                memcacheClient.set("max_job_id", "0")
                memcacheClient.set("max_handled_job_id", "0")

                memcacheClient.set("max_event_id", "0")
                memcacheClient.set("max_handled_event_id", "0")

                print "Connected to MemCache Daemon (PID %d)." \
                    % memcacheDaemonPid
                print "Waiting for MyData client(s) to connect..."
            else:
                raise Exception("MyData can't write to MemCache Daemon")
        else:
            logger.debug("MemCache Daemon is not running.")
            logger.debug("Since we're running MyData with --daemon, "
                         "we should start up a MemCache Daemon process!")
            memcacheDaemon.Start()
            memcacheDaemonPid = memcacheDaemon.GetPid()
            if memcacheDaemonPid:
                success = memcacheClient.set('test_key', 'test_value')
                memcacheClient.delete('test_key')
                if success:
                    memcacheClient.set("daemon_pid", str(os.getpid()))
                    self.namespace = "%s_%d_" % (self.name, os.getpid())
                    memcacheClient.set_namespace("%s" % self.namespace)

                    memcacheClient.set("clients", [])
                    clients = memcacheClient.get("clients")

                    memcacheClient.set("max_job_id", "0")
                    memcacheClient.set("max_handled_job_id", "0")

                    memcacheClient.set("max_event_id", "0")
                    memcacheClient.set("max_handled_event_id", "0")

                    print "Connected to MemCache Daemon (PID %d)." \
                        % memcacheDaemonPid
                    print "Waiting for MyData client(s) to connect..."
                else:
                    raise Exception("MyData can't write to MemCache Daemon")
            else:
                raise Exception("MyData daemon tried to start MemCache Daemon "
                                "but failed.")

    def run(self):
        self.memcacheClient = MemCache.MemCacheClient(['127.0.0.1:11211'],
                                                      namespace=self.namespace,
                                                      debug=0)
        previousClients = []

        # MyData daemon's main loop:
        while True:
            clients = self.memcacheClient.get("clients")
            if clients != previousClients:
                logger.debug("clients: " + str(clients))
                for client in clients:
                    if client not in previousClients:
                        print "A MyData client with PID %s has connected." \
                            % client
            previousClients = clients
            for client in clients:
                if not PidIsRunning(client):
                    logger.debug("Removing PID %d from clients list, "
                                 "because it is no longer running."
                                 % int(client))
                    clients.remove(client)
                    print "The MyData client with PID %s has disconnected." \
                        % client
                    self.memcacheClient.set("clients", clients)

            # Jobs are requests coming from the MyData client GUI to be
            # processed by the MyData daemon:
            try:
                maxJobId = int(self.memcacheClient.get("max_job_id"))
            except:
                maxJobId = 0
            try:
                maxHandledJobId = \
                    int(self.memcacheClient.get("max_handled_job_id"))
            except:
                maxHandledJobId = 0
            for jobId in range(maxHandledJobId + 1,
                               maxJobId + 1):
                job = self.memcacheClient.get("job_%d" % jobId)
                if job:
                    logger.debug("job_%d: %s" % (jobId, str(job)))
                    # Start job
                    if job['methodName'] == 'OnRefresh':
                        wx.CallAfter(wx.GetApp().OnRefresh, event=None,
                                     settingsModel=job['settingsModel'])
                        self.memcacheClient.incr("max_handled_job_id")

            # Events are progress updates coming from the MyData daemon
            # to be displayed by the MyData client GUI:
            try:
                maxEventId = int(self.memcacheClient.get("max_event_id"))
            except:
                maxEventId = 0
            try:
                maxHandledEventId = \
                    int(self.memcacheClient.get("max_handled_event_id"))
            except:
                maxHandledEventId = 0
            for eventId in range(maxHandledEventId + 1,
                                 maxEventId + 1):
                event = self.memcacheClient.get("event_%d" % eventId)
                if event:
                    logger.debug("event_%d: %s" % (eventId, str(event)))
