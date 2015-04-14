import threading
from random import randint
import time
import os
import wx

import MemCache
from Util import PidIsRunning
from logger.Logger import logger


class Client(threading.Thread):
    def __init__(self, name, mydataDaemonPid):
        threading.Thread.__init__(self)
        self.name = name
        self.mydataDaemonPid = mydataDaemonPid
        self.namespace = "%s_%d_" % (self.name, self.mydataDaemonPid)
        memcacheClient = MemCache.MemCacheClient(['127.0.0.1:11211'],
                                                 namespace=self.namespace,
                                                 debug=0)
        memcacheDaemon = MemCache.MemCacheDaemon()
        self.memcacheDaemonPid = memcacheDaemon.GetPid()
        if self.memcacheDaemonPid:
            success = memcacheClient.set('test_key', 'test_value')
            memcacheClient.delete('test_key')
            if success:
                print "Connected to MemCache Daemon (PID %d)." \
                    % self.memcacheDaemonPid
                print "Connected to MyData Daemon (PID %d)." \
                    % self.mydataDaemonPid
            else:
                raise Exception("MyData can't write to MemCache Daemon")
        else:
            raise Exception("MemCache Daemon is not running. "
                            "Since we're running MyData with --client, we "
                            "need a MemCache Daemon process to connect to!")
 
    def run(self):
        print "\nTO DO: Client should be able to retrieve already-running " \
                "state from daemon (e.g. 'displaying 10 uploads in " \
                "progress'), rather than just retrieving incremental " \
                "updates ('AddRow') from the daemon.\n"
        logger.debug("namespace: " + self.namespace)
        self.memcacheClient = MemCache.MemCacheClient(['127.0.0.1:11211'],
                                                      namespace=self.namespace,
                                                      debug=0)

        mainLoopCount = 0
        # MyData Client's main loop:
        while True:
            mainLoopCount += 1
            if not PidIsRunning(self.memcacheDaemonPid):
                logger.error("MemCache daemon stopped running!")
                wx.GetApp().ExitOnCriticalFailure(
                    preamble="The MyData Client must exit, because " \
                        "the connection to the MemCache daemon has been lost.",
                    reason="The MemCache daemon (PID %d) appears to have " \
                            "stopped running.  Feel free to relaunch the "
                            "MyData client to try reconnecting." \
                            % self.memcacheDaemonPid)

            if not PidIsRunning(self.mydataDaemonPid):
                logger.error("MyData daemon stopped running!")
                wx.GetApp().ExitOnCriticalFailure(
                    preamble="The MyData Client must exit, because " \
                        "the connection to the MyData daemon has been lost.",
                    reason="The MyData daemon (PID %d) appears to have " \
                            "stopped running.  Feel free to relaunch the "
                            "MyData client to try reconnecting." \
                            % self.mydataDaemonPid)

            # Events are progress updates coming from the MyData daemon to be
            # displayed by the MyData client GUI:
            try:
                maxEventId = int(self.memcacheClient.get("max_event_id"))
            except:
                maxEventId = 0
            try:
                maxHandledEventId = \
                    int(self.memcacheClient.get("max_handled_event_id"))
            except:
                maxHandledEventId = 0
            for eventId in range(maxHandledEventId + 1, maxEventId + 1):
                # Process event
                event = self.memcacheClient.get("event_%d" % eventId)
                if not event:
                    continue
                if event['eventType'] == 'IncrementProgressDialog':
                    def incrementProgressDialog():
                        mydataApp = wx.GetApp()
                        mydataApp.GetProgressDialog()\
                            .SetMaxValue(event['totalNumUserOrGroupFolders'])
                        mydataApp.GetProgressDialog().Show()
                        mydataApp.IncrementProgressDialog(daemonEvent=event)
                        mydataApp.progressDialog\
                            .Update(event['numUserOrGroupFoldersScanned'],
                                    event['message'])
                        if event['numUserOrGroupFoldersScanned'] == \
                                event['totalNumUserOrGroupFolders']:
                            mydataApp.CloseProgressDialog()
                    wx.CallAfter(incrementProgressDialog)
                elif event['eventType'] == 'UsersModel.AddRow':
                    if not wx.GetApp().usersModel\
                            .ContainsDataViewId(event['userRecord']
                                                .GetDataViewId()):
                        wx.CallAfter(wx.GetApp().usersModel.AddRow,
                                     event['userRecord'])
                elif event['eventType'] == 'FoldersModel.AddRow':
                    if not wx.GetApp().foldersModel\
                            .ContainsDataViewId(event['folderModel']
                                                .GetDataViewId()):
                        wx.CallAfter(wx.GetApp().foldersModel.AddRow,
                                     event['folderModel'])
                elif event['eventType'] == 'VerificationsModel.AddRow':
                    if not wx.GetApp().verificationsModel\
                            .ContainsDataViewId(event['verificationModel']
                                                .GetDataViewId()):
                        wx.CallAfter(wx.GetApp().verificationsModel.AddRow,
                                     event['verificationModel'])
                elif event['eventType'] == 'UploadsModel.AddRow':
                    if not wx.GetApp().uploadsModel\
                            .ContainsDataViewId(event['uploadModel']
                                                .GetDataViewId()):
                        wx.CallAfter(wx.GetApp().uploadsModel.AddRow,
                                     event['uploadModel'])
                elif event['eventType'] == 'SetStatusMessage':
                    wx.CallAfter(wx.GetApp().GetMainFrame().SetStatusMessage,
                                 event['message'])
                elif event['eventType'] == 'VerificationsModel.MessageUpdated':
                    wx.CallAfter(wx.GetApp().verificationsModel.MessageUpdated,
                                 event['verificationModel'])
                elif event['eventType'] == 'FoldersModel.StatusUpdated':
                    wx.CallAfter(wx.GetApp().foldersModel.StatusUpdated,
                                 event['folderModel'])
                elif event['eventType'] == 'UploadsModel.FileSizeUpdated':
                    wx.CallAfter(wx.GetApp().uploadsModel.FileStatusUpdated,
                                 event['uploadModel'])
                elif event['eventType'] == 'UploadsModel.ProgressUpdated':
                    wx.CallAfter(wx.GetApp().uploadsModel.ProgressUpdated,
                                 event['uploadModel'])
                elif event['eventType'] == 'UploadsModel.StatusUpdated':
                    wx.CallAfter(wx.GetApp().uploadsModel.StatusUpdated,
                                 event['uploadModel'])
                elif event['eventType'] == 'UploadsModel.MessageUpdated':
                    wx.CallAfter(wx.GetApp().uploadsModel.MessageUpdated,
                                 event['uploadModel'])
                elif event['eventType'] == \
                        'FoldersController.ShowMessageDialog':
                    wx.PostEvent(
                        wx.GetApp().GetMainFrame(),
                        wx.GetApp().foldersController.ShowMessageDialogEvent(
                            title="MyData Client",
                            message=event['message'],
                            icon=event['icon']))
                else:
                    continue
                self.memcacheClient.incr("max_handled_event_id")
                if event['eventType'] == 'VerificationsModel.AddRow':
                    logger.debug("Handled event of type: %s with filename: %s"
                                % (event['eventType'],
                                   event['verificationModel'].GetFilename()))
                else:
                    logger.debug("Handled event of type: %s"
                                 % event['eventType'])
