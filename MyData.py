import sys
import wx
import wx.aui
import webbrowser
import os
import appdirs
import traceback
import threading
import argparse
from datetime import datetime
import logging

import CommitDef
import MyDataVersionNumber
from FoldersView import FoldersView
from FoldersModel import FoldersModel
from FoldersController import FoldersController
from UsersView import UsersView
from UsersModel import UsersModel
# from GroupsView import GroupsView
from GroupsModel import GroupsModel
from VerificationsView import VerificationsView
from VerificationsModel import VerificationsModel
from UploadsView import UploadsView
from UploadsModel import UploadsModel
from UploaderModel import UploaderModel
from LogView import LogView
from SettingsModel import SettingsModel
from SettingsDialog import SettingsDialog
from Exceptions import NoActiveNetworkInterface
from Exceptions import InvalidFolderStructure
from EnhancedStatusBar import EnhancedStatusBar
from logger.Logger import logger
from MyDataTaskBarIcon import MyDataTaskBarIcon
from MyDataProgressDialog import MyDataProgressDialog
import MyDataEvents as mde
import MemCache


class NotebookTabs:
    FOLDERS = 0
    USERS = 1
    GROUPS = 2
    VERIFICATIONS = 3
    UPLOADS = 4


class MyDataFrame(wx.Frame):
    def __init__(self, parent, id, title, style, settingsModel):
        wx.Frame.__init__(self, parent, id, title, style=style)
        self.settingsModel = settingsModel
        self.SetSize(wx.Size(1000, 600))
        self.statusbar = EnhancedStatusBar(self, wx.ID_ANY)
        if sys.platform.startswith("win"):
            self.statusbar.SetSize(wx.Size(-1, 28))
        else:
            self.statusbar.SetSize(wx.Size(-1, 18))
        self.statusbar.SetFieldsCount(2)
        self.SetStatusBar(self.statusbar)
        self.statusbar.SetStatusWidths([-1, 60])
        if hasattr(sys, "frozen"):
            sysExecutableDir = os.path.dirname(sys.executable)
            if sys.platform.startswith("darwin"):
                pngNormalPath = "png-normal"
            else:
                pngNormalPath = os.path.join(sysExecutableDir, "png-normal")
        else:
            myDataModuleDir = os.path.dirname(os.path.realpath(__file__))
            pngNormalPath = os.path.join(myDataModuleDir, "png-normal")
        if sys.platform.startswith("win"):
            iconSubdir = "icons24x24"
        else:
            iconSubdir = "icons16x16"
        self.connectedBitmap = \
            wx.Image(os.path.join(pngNormalPath, iconSubdir, "Connect.png"),
                     wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        self.disconnectedBitmap = \
            wx.Image(os.path.join(pngNormalPath,
                                  iconSubdir, "Disconnect.png"),
                     wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        self.connected = False
        self.SetConnected(settingsModel.GetMyTardisUrl(), False)

    def FolderScansAndUploadsAreRunning(self):
        return wx.GetApp().FolderScansAndUploadsAreRunning()

    def SetFolderScansAndUploadsRunning(self, folderScansAndUploadsRunning):
        wx.GetApp()\
            .SetFolderScansAndUploadsRunning(folderScansAndUploadsRunning)

    def SetStatusMessage(self, message):
        if self.settingsModel.RunningAsDaemon():
            max_event_id = wx.GetApp().memcacheClient.get("max_event_id")
            if max_event_id is not None:
                wx.GetApp().memcacheClient.incr("max_event_id")
                event_id = int(wx.GetApp().memcacheClient.get("max_event_id"))
                daemonEvent = \
                    {"eventType": "SetStatusMessage",
                     "message": message}
                wx.GetApp().memcacheClient.set("event_%d" % event_id,
                                               daemonEvent)
            else:
                raise Exception("Didn't find max_event_id in namespace %s"
                                % wx.GetApp().memcacheClient.get_namespace())
        else:
            self.statusbar.SetStatusMessage(message)

    def SetConnected(self, myTardisUrl, connected):
        if self.connected == connected:
            return

        self.myTardisUrl = myTardisUrl
        self.connected = connected

        if self.myTardisUrl != self.settingsModel.GetMyTardisUrl():
            # This probably came from an old thread which took a while to
            # return a connection error.  While it was attempting to connect,
            # the user may have corrected the MyTardis URL in the Settings
            # dialog.
            return

        if connected:
            if sys.platform.startswith("win"):
                self.statusbar.SetStatusConnectionIcon(self.connectedBitmap)
            self.SetStatusMessage("Connected to " + myTardisUrl)
        else:
            if sys.platform.startswith("win"):
                self.statusbar.SetStatusConnectionIcon(self.disconnectedBitmap)
            self.SetStatusMessage("Not connected to " + myTardisUrl)


class MyData(wx.App):
    def __init__(self, name):
        self.name = name
        wx.App.__init__(self, redirect=False)

    def OnInit(self):
        logger.debug("MyData version:   " +
                     MyDataVersionNumber.versionNumber)
        logger.debug("MyData commit:  " + CommitDef.LATEST_COMMIT)
        appname = "MyData"
        appauthor = "Monash University"
        appdirPath = appdirs.user_data_dir(appname, appauthor)
        logger.debug("appdirPath: " + appdirPath)
        if not os.path.exists(appdirPath):
            os.makedirs(appdirPath)

        self.lastNetworkConnectivityCheckTime = datetime.fromtimestamp(0)
        self.lastNetworkConnectivityCheckSuccess = False
        self.activeNetworkInterface = None

        # MyData.cfg stores settings in INI format, readable by ConfigParser
        self.SetConfigPath(os.path.join(appdirPath, appname + '.cfg'))
        logger.debug("self.GetConfigPath(): " + self.GetConfigPath())

        self.settingsModel = SettingsModel(self.GetConfigPath())

        parser = argparse.ArgumentParser()
        mode = parser.add_mutually_exclusive_group(required=False)
        mode.add_argument("-b", "--background", action="store_true",
                          help="Begin folder scans and uploads with "
                               "previously saved settings, instead of "
                               "prompting the user to confirm settings. "
                               "Start with MyData minimized to system tray.")
        mode.add_argument("-c", "--client", action="store_true",
                          help="Connect to a MyData daemon process.  The "
                               "client process is responsible for the GUI "
                               "and the daemon process is responsible for "
                               "the folder scans and data uploads.")
        mode.add_argument("-d", "--daemon", action="store_true",
                          help="Run a MyData daemon which can run as a "
                               "service and be connected to by a MyData "
                               "client GUI.  The daemon process can run as "
                               "a service and persist beyond user login "
                               "sessions.")
        parser.add_argument("-v", "--version", action="store_true",
                            help="Display MyData version and exit")
        parser.add_argument("-l", "--loglevel", help="set logging verbosity")
        args, unknown = parser.parse_known_args()
        if args.version:
            print "MyData %s" % MyDataVersionNumber.versionNumber
            os._exit(0)
        self.settingsModel.SetBackgroundMode(args.background)

        if args.daemon or args.client:
            self.memcacheClient = MemCache.MemCacheClient(['127.0.0.1:11211'],
                                                          namespace="MyData_",
                                                          debug=0)
            self.memcacheDaemon = MemCache.MemCacheDaemon()
        if args.daemon:
            print "MyData Daemon %s (PID %d)" \
                % (MyDataVersionNumber.versionNumber, os.getpid())
            self.settingsModel.SetRunningAsDaemon(True)
            logger.SetLogFileName(".MyData_daemon_debug_log.txt")
            self.memcacheClient.set_namespace("%s_%d_"
                                              % (self.name, os.getpid()))
            from Daemon import Daemon
            self.daemon = Daemon(self.name)
            self.daemon.start()

        if args.client:
            print "MyData Client %s (PID %d)" \
                % (MyDataVersionNumber.versionNumber, os.getpid())
            self.settingsModel.SetRunningAsClient(True)
            logger.SetLogFileName(".MyData_client_debug_log.txt")
            logger.debug("Running MyData in client mode...")
            logger.debug("Checking if MemCache Daemon is running...")
            self.memcacheClient.set_namespace("%s_" % self.name)
            pid = self.memcacheDaemon.GetPid()
            if pid:
                success = self.memcacheClient.set('test_key', 'test_value')
                self.memcacheClient.delete('test_key')
                if success:
                    daemon_pid = self.memcacheClient.get("daemon_pid")
                    if daemon_pid:
                        daemon_pid = int(daemon_pid)
                        from Util import PidIsRunning
                        if not PidIsRunning(daemon_pid):
                            print "\nERROR: The MyData daemon whose PID " \
                                    "(%d) was found in MemCache is " \
                                    "not running." % daemon_pid
                            os._exit(1)
                    else:
                        raise Exception("Daemon PID was not found in "
                                        "MemCache.")
                    namespace = "%s_%d_" % (self.name, daemon_pid)
                    self.memcacheClient.set_namespace("%s" % namespace)

                    clients = self.memcacheClient.get("clients")
                    if clients is not None:
                        clients.append(os.getpid())
                        self.memcacheClient.set("clients", clients)
                        clients = self.memcacheClient.get("clients")
                        from Client import Client
                        self.client = Client(self.name, daemon_pid)
                        self.client.start()
                    else:
                        raise Exception("Didn't find clients in namespace")
                else:
                    raise Exception("MyData can't write to MemCache Daemon.")
            else:
                raise Exception("MemCache Daemon is not running.")
        else:
            # Using wx.SingleInstanceChecker to check whether MyData is already
            # running.
            # Running MyData --version is allowed when MyData is already
            # running, in fact this is used by calls to ShellExecuteEx to
            # test user privilege elevation on Windows.
            # A workaround for the 'Deleted stale lock file' issue with
            # SingleInstanceChecker on Mac OS X is to lower the wx logging
            # level.  MyData doesn't use wx.Log
            wx.Log.SetLogLevel(wx.LOG_Error)
            self.instance = wx.SingleInstanceChecker(self.name,
                                                     path=appdirPath)
            if self.instance.IsAnotherRunning():
                wx.MessageBox("MyData is already running!", "MyData",
                              wx.ICON_ERROR)
                return False
        if args.loglevel:
            if args.loglevel == "DEBUG":
                logger.SetLevel(logging.DEBUG)
            elif args.loglevel == "INFO":
                logger.SetLevel(logging.INFO)
            elif args.loglevel == "WARN":
                logger.SetLevel(logging.WARN)
            elif args.loglevel == "ERROR":
                logger.SetLevel(logging.ERROR)

        if sys.platform.startswith("darwin"):
            # On Mac OS X, adding an Edit menu seems to help with
            # enabling command-c (copy) and command-v (paste)
            self.menuBar = wx.MenuBar()
            self.editMenu = wx.Menu()
            self.editMenu.Append(wx.ID_UNDO, "Undo\tCTRL+Z", "Undo")
            self.Bind(wx.EVT_MENU, self.OnUndo, id=wx.ID_UNDO)
            self.editMenu.Append(wx.ID_REDO, "Redo\tCTRL+SHIFT+Z", "Redo")
            self.Bind(wx.EVT_MENU, self.OnRedo, id=wx.ID_REDO)
            self.editMenu.AppendSeparator()
            self.editMenu.Append(wx.ID_CUT, "Cut\tCTRL+X",
                                 "Cut the selected text")
            self.Bind(wx.EVT_MENU, self.OnCut, id=wx.ID_CUT)
            self.editMenu.Append(wx.ID_COPY, "Copy\tCTRL+C",
                                 "Copy the selected text")
            self.Bind(wx.EVT_MENU, self.OnCopy, id=wx.ID_COPY)
            self.editMenu.Append(wx.ID_PASTE, "Paste\tCTRL+V",
                                 "Paste text from the clipboard")
            self.Bind(wx.EVT_MENU, self.OnPaste, id=wx.ID_PASTE)
            self.editMenu.Append(wx.ID_SELECTALL, "Select All\tCTRL+A",
                                 "Select All")
            self.Bind(wx.EVT_MENU, self.OnSelectAll, id=wx.ID_SELECTALL)
            self.menuBar.Append(self.editMenu, "Edit")

            self.Bind(wx.EVT_MENU, self.OnCloseFrame, id=wx.ID_EXIT)

            self.helpMenu = wx.Menu()

            helpMenuItemID = wx.NewId()
            self.helpMenu.Append(helpMenuItemID, "&MyData Help")
            self.Bind(wx.EVT_MENU, self.OnHelp, id=helpMenuItemID)

            walkthroughMenuItemID = wx.NewId()
            self.helpMenu.Append(walkthroughMenuItemID,
                                 "Mac OS X &Walkthrough")
            self.Bind(wx.EVT_MENU, self.OnWalkthrough,
                      id=walkthroughMenuItemID)

            self.helpMenu.Append(wx.ID_ABOUT,   "&About MyData")
            self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)
            self.menuBar.Append(self.helpMenu, "&Help")

        self.usersModel = UsersModel(self.settingsModel)
        self.groupsModel = GroupsModel(self.settingsModel)
        self.foldersModel = FoldersModel(self.usersModel, self.groupsModel,
                                         self.settingsModel)
        self.usersModel.SetFoldersModel(self.foldersModel)
        self.verificationsModel = VerificationsModel(self.settingsModel)
        self.uploadsModel = UploadsModel(self.settingsModel)

        self.frame = MyDataFrame(None, -1, self.name,
                                 style=wx.DEFAULT_FRAME_STYLE,
                                 settingsModel=self.settingsModel)
        if sys.platform.startswith("darwin"):
            self.frame.SetMenuBar(self.menuBar)
        self.myDataEvents = mde.MyDataEvents(notifyWindow=self.frame)

        self.SetFolderScansAndUploadsRunning(False)
        if self.settingsModel.RunningAsClient() or \
                self.settingsModel.RunningAsDaemon():
            self.memcacheClient.set("folderScansAndUploadsRunning", False)

        self.taskBarIcon = MyDataTaskBarIcon(self.frame, self.settingsModel)

        wx.EVT_TASKBAR_LEFT_UP(self.taskBarIcon, self.OnTaskBarLeftClick)

        self.frame.Bind(wx.EVT_CLOSE, self.OnCloseFrame)
        self.frame.Bind(wx.EVT_ICONIZE, self.OnMinimizeFrame)

        img = wx.Image("favicon.ico", wx.BITMAP_TYPE_ANY)
        bmp = wx.BitmapFromImage(img)
        icon = wx.EmptyIcon()
        icon.CopyFromBitmap(bmp)
        self.frame.SetIcon(icon)

        self.panel = wx.Panel(self.frame)

        self.foldersUsersNotebook = \
            wx.aui.AuiNotebook(self.panel,
                               style=wx.aui.AUI_NB_TOP |
                               wx.aui.AUI_NB_SCROLL_BUTTONS)
        self.Bind(wx.aui.EVT_AUINOTEBOOK_PAGE_CHANGING,
                  self.OnNotebookPageChanging, self.foldersUsersNotebook)

        self.foldersView = FoldersView(self.foldersUsersNotebook,
                                       foldersModel=self.foldersModel)

        self.foldersUsersNotebook.AddPage(self.foldersView, "Folders")
        self.foldersController = \
            FoldersController(self.frame,
                              self.foldersModel,
                              self.foldersView,
                              self.usersModel,
                              self.verificationsModel,
                              self.uploadsModel,
                              self.settingsModel)

        self.usersView = UsersView(self.foldersUsersNotebook,
                                   usersModel=self.usersModel)
        self.foldersUsersNotebook.AddPage(self.usersView, "Users")

        # self.groupsView = GroupsView(self.foldersUsersNotebook,
        #                              groupsModel=self.groupsModel)
        # self.foldersUsersNotebook.AddPage(self.groupsView, "Groups")

        self.verificationsView = \
            VerificationsView(self.foldersUsersNotebook,
                              verificationsModel=self.verificationsModel,
                              foldersController=self.foldersController)
        self.foldersUsersNotebook.AddPage(self.verificationsView,
                                          "Verifications")

        self.uploadsView = \
            UploadsView(self.foldersUsersNotebook,
                        uploadsModel=self.uploadsModel,
                        foldersController=self.foldersController)
        self.foldersUsersNotebook.AddPage(self.uploadsView, "Uploads")

        self.logView = LogView(self.foldersUsersNotebook, self.settingsModel)
        self.foldersUsersNotebook.AddPage(self.logView, "Log")

        self.CreateToolbar()

        sizer = wx.BoxSizer()
        sizer.Add(self.foldersUsersNotebook, 1, flag=wx.EXPAND)
        self.panel.SetSizer(sizer)

        sizer = wx.BoxSizer()
        sizer.Add(self.panel, 1, flag=wx.EXPAND)
        self.frame.SetSizer(sizer)

        self.foldersUsersNotebook.SendSizeEvent()

        self.panel.SetFocus()

        self.SetTopWindow(self.frame)

        if not self.settingsModel.RunningAsDaemon():
            # print "Showing main frame"
            self.frame.Show(True)
        else:
            logger.debug("Running as a daemon, so not showing main frame")

        event = None
        if not self.settingsModel.RunningAsDaemon():
            logger.debug("Not running as a daemon, so checking whether we "
                         "should display settings dialog.")
            if self.settingsModel.RunningAsClient():
                logger.debug("Running as a client, so we need to check what "
                             "state the daemon is in to determine whether it "
                             "is appropriate to display the settings dialog.")
                folderScansAndUploadsRunning = \
                    self.memcacheClient.get("folderScansAndUploadsRunning")
                if folderScansAndUploadsRunning:
                    logger.debug("Folder scans and uploads are already running"
                                 "in the daemon, so we won't display MyData's "
                                 "settings dialog.")
                    return True
                else:
                    logger.debug("OnRefresh() is not running in the daemon, "
                                 "so it's OK to display MyData's settings "
                                 "dialog.")
            self.progressDialog = \
                MyDataProgressDialog(self.frame, wx.ID_ANY, userCanAbort=True)

            if self.settingsModel.RequiredFieldIsBlank():
                self.OnSettings(event)
            else:
                self.frame.SetTitle("MyData - " +
                                    self.settingsModel.GetInstrumentName())
                if self.settingsModel.RunningInBackgroundMode():
                    self.frame.Iconize()
                    self.OnRefresh(event)
                else:
                    self.OnSettings(event)
        else:
            logger.debug("Running as a daemon, so not showing "
                         "settings dialog.")

        return True

    def GetProgressDialog(self):
        return self.progressDialog

    def OnUndo(self, event):
        print "OnUndo"
        textCtrl = wx.Window.FindFocus()
        if textCtrl is not None:
            print "Calling textCtrl.Undo()"
            textCtrl.Undo()

    def OnRedo(self, event):
        textCtrl = wx.Window.FindFocus()
        if textCtrl is not None:
            textCtrl.Redo()

    def OnCut(self, event):
        textCtrl = wx.Window.FindFocus()
        if textCtrl is not None:
            textCtrl.Cut()

    def OnCopy(self, event):
        textCtrl = wx.Window.FindFocus()
        if textCtrl is not None:
            textCtrl.Copy()

    def OnPaste(self, event):
        textCtrl = wx.Window.FindFocus()
        if textCtrl is not None:
            textCtrl.Paste()

    def OnSelectAll(self, event):
        textCtrl = wx.Window.FindFocus()
        if textCtrl is not None:
            textCtrl.SelectAll()

    def OnTaskBarLeftClick(self, evt):
        self.taskBarIcon.PopupMenu(self.taskBarIcon.CreatePopupMenu())

    def OnCloseFrame(self, event):
        """
        If running in background mode, don't actually close it,
        just iconize it.
        """
        if self.settingsModel.RunningInBackgroundMode():
            self.frame.Show()  # See: http://trac.wxwidgets.org/ticket/10426
            self.frame.Hide()
        else:
            started = self.foldersController.Started()
            completed = self.foldersController.Completed()
            canceled = self.foldersController.Canceled()
            failed = self.foldersController.Failed()

            message = "Are you sure you want to close MyData?"
            if started and not completed and not canceled and not failed:
                message += "\n\n" \
                    "MyData will attempt to shut down any uploads currently " \
                    "in progress before exiting."
            confirmationDialog = \
                wx.MessageDialog(None, message, "MyData",
                                 wx.YES | wx.NO | wx.ICON_QUESTION)
            okToExit = confirmationDialog.ShowModal()
            if okToExit == wx.ID_YES:
                def shutDownDataScansAndUploads():
                    logger.debug("Starting run() method for thread %s"
                                 % threading.current_thread().name)
                    try:
                        wx.CallAfter(wx.BeginBusyCursor)
                        self.foldersController.ShutDownUploadThreads()

                        def endBusyCursorIfRequired():
                            try:
                                wx.EndBusyCursor()
                            except wx._core.PyAssertionError, e:
                                if "no matching wxBeginBusyCursor()" \
                                        not in str(e):
                                    logger.error(str(e))
                                    raise
                        wx.CallAfter(endBusyCursorIfRequired)
                        os._exit(0)
                    except:
                        logger.debug(traceback.format_exc())
                        os._exit(1)
                    logger.debug("Finishing run() method for thread %s"
                                 % threading.current_thread().name)

                thread = threading.Thread(target=shutDownDataScansAndUploads)
                logger.debug("Starting thread %s" % thread.name)
                thread.start()
                logger.debug("Started thread %s" % thread.name)

    def ExitOnCriticalFailure(self, preamble=None, reason=None):
        """
        Used when MyData is running in --client mode and the connection is
        lost to the MyData daemon or the MemCache daemon.

        """
        if preamble:
            message = preamble
        else:
            message = "MyData must now exit, due to a critical failure."
        if reason:
            message = message + "\n\n" + reason
        errorDialog = wx.MessageDialog(None, message, "MyData",
                                       wx.OK | wx.ICON_ERROR)
        errorDialog.ShowModal()
        os._exit(1)

    def OnMinimizeFrame(self, event):
        """
        When minimizing, hide the frame so it "minimizes to tray"
        """
        if event.Iconized():
            self.frame.Show()  # See: http://trac.wxwidgets.org/ticket/10426
            self.frame.Hide()
            # self.taskBarIcon.ShowBalloon("MyData",
            #                         "Click the MyData icon " +
            #                         "to access its menu.")

    def CreateToolbar(self):
        """
        Create a toolbar.
        """

        if hasattr(sys, "frozen"):
            sysExecutableDir = os.path.dirname(sys.executable)
            if sys.platform.startswith("darwin"):
                pngNormalPath = "png-normal"
            else:
                pngNormalPath = os.path.join(sysExecutableDir, "png-normal")
            if sys.platform.startswith("darwin"):
                pngHotPath = "png-hot"
            else:
                pngHotPath = os.path.join(sysExecutableDir, "png-hot")
        else:
            myDataModuleDir = os.path.dirname(os.path.realpath(__file__))
            pngNormalPath = os.path.join(myDataModuleDir, "png-normal")
            pngHotPath = os.path.join(myDataModuleDir, "png-hot")

        self.toolbar = self.frame.CreateToolBar()
        self.toolbar.SetToolBitmapSize(wx.Size(24, 24))  # sets icon size

        openIcon = wx.Image(os.path.join(pngNormalPath,
                                         "icons24x24", "Open folder.png"),
                            wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        openTool = self.toolbar.AddSimpleTool(wx.ID_ANY, openIcon, "Open",
                                              "Open folder")
        self.Bind(wx.EVT_MENU, self.OnOpen, openTool)

        self.toolbar.AddSeparator()

        refreshIcon = wx.Image(os.path.join(pngNormalPath,
                                            "icons24x24", "Refresh.png"),
                               wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        self.refreshTool = self.toolbar.AddSimpleTool(wx.ID_REFRESH,
                                                      refreshIcon,
                                                      "Refresh", "")
        self.toolbar.EnableTool(wx.ID_REFRESH, True)
        self.Bind(wx.EVT_TOOL, self.OnRefresh, self.refreshTool,
                  self.refreshTool.GetId())

        self.toolbar.AddSeparator()

        settingsIcon = wx.Image(os.path.join(pngHotPath,
                                             "icons24x24", "Settings.png"),
                                wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        self.settingsTool = self.toolbar.AddSimpleTool(wx.ID_ANY, settingsIcon,
                                                       "Settings", "")
        self.Bind(wx.EVT_TOOL, self.OnSettings, self.settingsTool)

        self.toolbar.AddSeparator()

        internetIcon = \
            wx.Image(os.path.join(pngNormalPath,
                                  "icons24x24", "Internet explorer.png"),
                     wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        self.myTardisTool = self.toolbar.AddSimpleTool(wx.ID_ANY, internetIcon,
                                                       "MyTardis", "")
        self.Bind(wx.EVT_TOOL, self.OnMyTardis, self.myTardisTool)

        self.toolbar.AddSeparator()

        aboutIcon = wx.Image(os.path.join(pngHotPath,
                                          "icons24x24", "About.png"),
                             wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        self.aboutTool = self.toolbar.AddSimpleTool(wx.ID_ANY, aboutIcon,
                                                    "About MyData", "")
        self.Bind(wx.EVT_TOOL, self.OnAbout, self.aboutTool)

        self.toolbar.AddSeparator()

        helpIcon = wx.Image(os.path.join(pngHotPath,
                                         "icons24x24", "Help.png"),
                            wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        self.helpTool = self.toolbar.AddSimpleTool(wx.ID_ANY, helpIcon,
                                                   "MyData User Guide", "")
        self.Bind(wx.EVT_TOOL, self.OnHelp, self.helpTool)

        self.toolbar.AddStretchableSpace()
        self.searchCtrl = wx.SearchCtrl(self.toolbar, size=wx.Size(200, -1),
                                        style=wx.TE_PROCESS_ENTER)
        self.searchCtrl.ShowSearchButton(True)
        self.searchCtrl.ShowCancelButton(True)

        self.Bind(wx.EVT_TEXT_ENTER, self.OnDoSearch, self.searchCtrl)
        self.Bind(wx.EVT_TEXT, self.OnDoSearch, self.searchCtrl)

        self.toolbar.AddControl(self.searchCtrl)

        # This basically shows the toolbar
        self.toolbar.Realize()

        # self.SetCallFilterEvent(True)

    # def OnSearchButton(self,event):
        # pass

    # def OnSearchCancel(self,event):
        # pass

    def OnDoSearch(self, event):
        if self.foldersUsersNotebook.GetSelection() == NotebookTabs.FOLDERS:
            self.foldersModel.Filter(event.GetString())
        elif self.foldersUsersNotebook.GetSelection() == NotebookTabs.USERS:
            self.usersModel.Filter(event.GetString())
        elif self.foldersUsersNotebook.GetSelection() == NotebookTabs.GROUPS:
            self.groupsModel.Filter(event.GetString())
        elif self.foldersUsersNotebook.GetSelection() == \
                NotebookTabs.VERIFICATIONS:
            self.verificationsModel.Filter(event.GetString())
        elif self.foldersUsersNotebook.GetSelection() == NotebookTabs.UPLOADS:
            self.uploadsModel.Filter(event.GetString())

    def FolderScansAndUploadsAreRunning(self):
        return self.folderScansAndUploadsRunning

    def SetFolderScansAndUploadsRunning(self, folderScansAndUploadsRunning):
        self.folderScansAndUploadsRunning = folderScansAndUploadsRunning
        if self.settingsModel.RunningAsClient() or \
                self.settingsModel.RunningAsDaemon():
            self.memcacheClient.set("folderScansAndUploadsRunning",
                                    folderScansAndUploadsRunning)

    def OnRefresh(self, event, settingsModel=None,
                  needToValidateSettings=True):
        if self.settingsModel.RunningAsClient():
            logger.debug("We should ask the daemon to run OnRefresh.")
            max_job_id = self.memcacheClient.get("max_job_id")
            if max_job_id is not None:
                self.memcacheClient.incr("max_job_id")
                job_id = int(self.memcacheClient.get("max_job_id"))
                jobDict = {"methodName": "OnRefresh",
                           "settingsModel": self.settingsModel,
                           "requested": datetime.now(),
                           }
                self.memcacheClient.set("job_%d" % job_id, jobDict)
                return
            else:
                raise Exception("Didn't find max_job_id in namespace %s"
                                % self.memcacheClient.get_namespace())
        shutdownForRefreshAlreadyComplete = False
        if settingsModel is None:
            settingsModel = self.settingsModel
        if event is None:
            if settingsModel.RunningInBackgroundMode():
                logger.debug("OnRefresh called automatically "
                             "from MyData's OnInit().")
            elif self.settingsModel.RunningAsDaemon():
                logger.debug("OnRefresh called automatically "
                             "from MyData's Daemon.py")
            else:
                logger.debug("OnRefresh called automatically from "
                             "OnSettings(), after displaying SettingsDialog.")
        elif event.GetId() == self.settingsTool.GetId():
            logger.debug("OnRefresh called automatically from "
                         "OnSettings(), after displaying SettingsDialog, "
                         "which was launched from MyData's toolbar.")
        elif event.GetId() == self.refreshTool.GetId():
            logger.debug("OnRefresh triggered by Refresh toolbar icon.")
        elif self.taskBarIcon.GetMyTardisSyncMenuItem() is not None and \
                event.GetId() == \
                self.taskBarIcon.GetMyTardisSyncMenuItem().GetId():
            logger.debug("OnRefresh triggered by 'MyTardis Sync' "
                         "task bar menu item.")
        elif event.GetId() == mde.EVT_SETTINGS_VALIDATION_FOR_REFRESH:
            logger.debug("OnRefresh called from "
                         "EVT_SETTINGS_VALIDATION_FOR_REFRESH event.")
        elif event.GetId() == mde.EVT_SHUTDOWN_FOR_REFRESH_COMPLETE:
            logger.debug("OnRefresh called from "
                         "EVT_SHUTDOWN_FOR_REFRESH_COMPLETE event.")
            shutdownForRefreshAlreadyComplete = True
        elif event.GetId() == mde.EVT_SETTINGS_VALIDATION_FOR_REFRESH_COMPLETE:
            logger.debug("OnRefresh called from "
                         "EVT_SETTINGS_VALIDATION_FOR_REFRESH_COMPLETE event.")
            shutdownForRefreshAlreadyComplete = True
        else:
            logger.debug("OnRefresh: event.GetId() = %d" % event.GetId())

        if hasattr(event, "needToValidateSettings") and \
                event.needToValidateSettings is False:
            needToValidateSettings = False
        if hasattr(event, "shutdownSuccessful") and event.shutdownSuccessful:
            shutdownForRefreshAlreadyComplete = True

        # Shutting down existing data scan and upload processes:

        if self.FolderScansAndUploadsAreRunning() and \
                not shutdownForRefreshAlreadyComplete:
            message = \
                "Shutting down existing data scan and upload processes..."
            logger.debug(message)
            self.frame.SetStatusMessage(message)

            shutdownForRefreshEvent = \
                mde.MyDataEvent(mde.EVT_SHUTDOWN_FOR_REFRESH,
                                foldersController=self.foldersController)
            logger.debug("Posting shutdownForRefreshEvent")
            wx.PostEvent(wx.GetApp().GetMainFrame(), shutdownForRefreshEvent)
            return

        # Reset the status message to the connection status:
        self.frame.SetConnected(settingsModel.GetMyTardisUrl(),
                                False)
        self.foldersController.SetShuttingDown(False)

        self.searchCtrl.SetValue("")

        # Network connectivity check:

        settingsValidationForRefreshEvent = \
            mde.MyDataEvent(mde.EVT_SETTINGS_VALIDATION_FOR_REFRESH)

        intervalSinceLastConnectivityCheck = \
            datetime.now() - self.lastNetworkConnectivityCheckTime
        # FIXME: Magic number of 30 seconds since last connectivity check.
        if intervalSinceLastConnectivityCheck.total_seconds() >= 30 or \
                not self.lastNetworkConnectivityCheckSuccess:
            logger.debug("Checking network connectivity...")
            checkConnectivityEvent = \
                mde.MyDataEvent(mde.EVT_CHECK_CONNECTIVITY,
                                settingsModel=settingsModel,
                                nextEvent=settingsValidationForRefreshEvent)
            logger.debug("Posting checkConnectivityEvent from OnRefresh...")
            wx.PostEvent(wx.GetApp().GetMainFrame(), checkConnectivityEvent)
            return

        # Settings validation:

        if needToValidateSettings:
            logger.debug("OnRefresh: needToValidateSettings is True.")
            self.frame.SetStatusMessage("Validating settings...")
            self.settingsValidation = None

            def validateSettings():
                logger.debug("Starting run() method for thread %s"
                             % threading.current_thread().name)
                try:
                    wx.CallAfter(wx.BeginBusyCursor)
                    self.uploaderModel = settingsModel.GetUploaderModel()
                    activeNetworkInterfaces = \
                        self.uploaderModel.GetActiveNetworkInterfaces()
                    if len(activeNetworkInterfaces) == 0:
                        message = "No active network interfaces." \
                            "\n\n" \
                            "Please ensure that you have an active " \
                            "network interface (e.g. Ethernet or WiFi)."

                        def showDialog():
                            dlg = wx.MessageDialog(None, message, "MyData",
                                                   wx.OK | wx.ICON_ERROR)
                            dlg.ShowModal()

                            def endBusyCursorIfRequired():
                                try:
                                    wx.EndBusyCursor()
                                except wx._core.PyAssertionError, e:
                                    if "no matching wxBeginBusyCursor()" \
                                            not in str(e):
                                        logger.error(str(e))
                                        raise
                            wx.CallAfter(endBusyCursorIfRequired)
                            self.frame.SetStatusMessage("")
                            self.frame.SetConnected(
                                settingsModel.GetMyTardisUrl(), False)
                        wx.CallAfter(showDialog)
                        return

                    self.settingsValidation = settingsModel.Validate()
                    settingsValidationForRefreshCompleteEvent = \
                        mde.MyDataEvent(
                            mde.EVT_SETTINGS_VALIDATION_FOR_REFRESH_COMPLETE,
                            needToValidateSettings=False)
                    wx.PostEvent(self.frame,
                                 settingsValidationForRefreshCompleteEvent)

                    def endBusyCursorIfRequired():
                        try:
                            wx.EndBusyCursor()
                        except wx._core.PyAssertionError, e:
                            if "no matching wxBeginBusyCursor()" not in str(e):
                                logger.error(str(e))
                                raise
                    wx.CallAfter(endBusyCursorIfRequired)
                except:
                    logger.debug(traceback.format_exc())
                    return
                logger.debug("Finishing run() method for thread %s"
                             % threading.current_thread().name)

            thread = threading.Thread(target=validateSettings,
                                      name="OnRefreshValidateSettings")
            logger.debug("Starting thread %s" % thread.name)
            thread.start()
            logger.debug("Started thread %s" % thread.name)
            return

        if needToValidateSettings and not self.settingsValidation.valid:
            logger.debug("Displaying result from settings validation.")
            message = self.settingsValidation.message
            logger.error(message)
            dlg = wx.MessageDialog(None, message, "MyData",
                                   wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            self.OnSettings(event)
            return

        if "Group" in settingsModel.GetFolderStructure():
            self.foldersView.ShowGroupColumn(True)
        else:
            self.foldersView.ShowGroupColumn(False)

        logger.debug("OnRefresh: Creating progress dialog.")

        if not self.settingsModel.RunningAsDaemon():
            self.progressDialog.Show()

        self.SetTotalNumUserOrGroupFolders(self.usersModel
                                           .GetNumUserOrGroupFolders())

        if self.settingsModel.RunningAsDaemon():
            logger.debug("Setting FolderScansAndUploadsRunning to True.")
        self.SetFolderScansAndUploadsRunning(True)

        # SECTION 4: Start FoldersModel.Refresh(),
        # followed by FoldersController.StartDataUploads().

        self.SetNumUserOrGroupFoldersScanned(0)

        def scanDataDirs():
            logger.debug("Starting run() method for thread %s"
                         % threading.current_thread().name)
            wx.CallAfter(self.frame.SetStatusMessage,
                         "Scanning data folders...")
            try:
                if self.settingsModel.RunningAsDaemon():
                    def ShouldAbort():
                        return False
                    self.foldersModel.Refresh(ShouldAbort)
                else:
                    self.foldersModel.Refresh(self.progressDialog.ShouldAbort)
            except InvalidFolderStructure, ifs:
                # Should not be raised when running in background mode.
                if not self.settingsModel.RunningAsDaemon():
                    wx.CallAfter(self.CloseProgressDialog)

                def showMessageDialog():
                    dlg = wx.MessageDialog(None, str(ifs), "MyData",
                                           wx.OK | wx.ICON_ERROR)
                    dlg.ShowModal()
                wx.CallAfter(showMessageDialog)
                self.frame.SetStatusMessage(str(ifs))
                return

            if not self.settingsModel.RunningAsDaemon():
                wx.CallAfter(self.CloseProgressDialog)

            def endBusyCursorIfRequired():
                try:
                    wx.EndBusyCursor()
                except wx._core.PyAssertionError, e:
                    if "no matching wxBeginBusyCursor()" not in str(e):
                        logger.error(str(e))
                        raise

            if self.ShouldAbort():
                wx.CallAfter(endBusyCursorIfRequired)
                return

            startDataUploadsEvent = \
                mde.MyDataEvent(mde.EVT_START_DATA_UPLOADS,
                                foldersController=self.foldersController)
            logger.debug("Posting startDataUploadsEvent")
            wx.PostEvent(wx.GetApp().GetMainFrame(), startDataUploadsEvent)

            wx.CallAfter(endBusyCursorIfRequired)
            logger.debug("Finishing run() method for thread %s"
                         % threading.current_thread().name)

        thread = threading.Thread(target=scanDataDirs,
                                  name="ScanDataDirectoriesThread")
        logger.debug("OnRefresh: Starting scanDataDirs thread.")
        thread.start()
        logger.debug("OnRefresh: Started scanDataDirs thread.")


    def ShouldAbort(self):
        if not self.settingsModel.RunningAsDaemon():
            return self.progressDialog.ShouldAbort()
        else:
            return False

    def CloseProgressDialog(self):
        self.progressDialog.Show(False)

    def IncrementProgressDialog(self, daemonEvent=None):
        if daemonEvent:
            for key in ['numUserOrGroupFoldersScanned',
                        'totalNumUserOrGroupFolders']:
                exec('%s = %d' % (key, daemonEvent[key]))
            for key in ['dataDirectory',
                        'message']:
                exec('%s = "%s"' % (key,
                                    daemonEvent[key].replace('"', '\\"')))
        else:
            numUserOrGroupFoldersScanned = \
                self.IncrementNumUserOrGroupFoldersScanned()
            totalNumUserOrGroupFolders = self.GetTotalNumUserOrGroupFolders()
            dataDirectory = self.settingsModel.GetDataDirectory()
            message = "Scanned %d of %d folders in %s" % (
                numUserOrGroupFoldersScanned,
                totalNumUserOrGroupFolders,
                self.settingsModel.GetDataDirectory())
        if self.settingsModel.RunningAsDaemon():
            max_event_id = wx.GetApp().memcacheClient.get("max_event_id")
            if max_event_id is not None:
                wx.GetApp().memcacheClient.incr("max_event_id")
                event_id = int(wx.GetApp().memcacheClient.get("max_event_id"))
                daemonEvent = \
                    {"eventType": "IncrementProgressDialog",
                     "numUserOrGroupFoldersScanned": 
                         numUserOrGroupFoldersScanned,
                     "totalNumUserOrGroupFolders": totalNumUserOrGroupFolders,
                     "dataDirectory": dataDirectory,
                     "message": message}
                wx.GetApp().memcacheClient.set("event_%d" % event_id,
                                               daemonEvent)
            else:
                raise Exception("Didn't find max_event_id in namespace %s"
                                % wx.GetApp().memcacheClient.get_namespace())

        if not self.settingsModel.RunningAsDaemon():
            self.progressDialog.Update(numUserOrGroupFoldersScanned,
                                       message)

    def CancelCallback(self):
        def shutDownUploadThreads():
            try:
                wx.CallAfter(wx.BeginBusyCursor)
                self.foldersController.ShutDownUploadThreads()

                def endBusyCursorIfRequired():
                    try:
                        wx.EndBusyCursor()
                    except wx._core.PyAssertionError, e:
                        if "no matching wxBeginBusyCursor()" not in str(e):
                            logger.error(str(e))
                            raise
                wx.CallAfter(endBusyCursorIfRequired)
            except:
                logger.error(traceback.format_exc())
        thread = threading.Thread(target=shutDownUploadThreads)
        thread.start()

    def SetNumUserOrGroupFoldersScanned(self, numUserOrGroupFoldersScanned):
        self.numUserOrGroupFoldersScanned = numUserOrGroupFoldersScanned

    def GetNumUserOrGroupFoldersScanned(self):
        return self.numUserOrGroupFoldersScanned

    def IncrementNumUserOrGroupFoldersScanned(self):
        self.numUserOrGroupFoldersScanned = \
            self.numUserOrGroupFoldersScanned + 1
        return self.numUserOrGroupFoldersScanned

    def SetTotalNumUserOrGroupFolders(self, totalNumUserOrGroupFolders):
        self.totalNumUserOrGroupFolders = totalNumUserOrGroupFolders

    def GetTotalNumUserOrGroupFolders(self):
        return self.totalNumUserOrGroupFolders

    def OnOpen(self, event):
        if self.foldersUsersNotebook.GetSelection() == NotebookTabs.FOLDERS:
            self.foldersController.OnOpenFolder(event)

    def OnDelete(self, event):
        if self.foldersUsersNotebook.GetSelection() == NotebookTabs.FOLDERS:
            self.foldersController.OnDeleteFolders(event)
        else:
            self.usersView.OnDeleteUsers(event)

    def OnNotebookPageChanging(self, event):
        if hasattr(self, 'searchCtrl'):
            self.searchCtrl.SetValue("")

    def OnSettings(self, event):
        settingsDialog = SettingsDialog(self.frame, -1, "Settings",
                                        self.settingsModel,
                                        size=wx.Size(400, 400),
                                        style=wx.DEFAULT_DIALOG_STYLE)
        if settingsDialog.ShowModal() == wx.ID_OK:
            logger.debug("settingsDialog.ShowModal() returned wx.ID_OK")
            myTardisUrlChanged = (self.settingsModel.GetMyTardisUrl() !=
                                  settingsDialog.GetMyTardisUrl())
            if myTardisUrlChanged:
                self.frame.SetConnected(settingsDialog.GetMyTardisUrl(), False)
            self.frame.SetTitle("MyData - " +
                                self.settingsModel.GetInstrumentName())
            if self.settingsModel.RunningAsClient():
                logger.debug("Now we should ask the daemon to run OnRefresh.")
                max_job_id = self.memcacheClient.get("max_job_id")
                if max_job_id is not None:
                    self.memcacheClient.incr("max_job_id")
                    job_id = int(self.memcacheClient.get("max_job_id"))
                    jobDict = {"methodName": "OnRefresh",
                               "settingsModel": self.settingsModel,
                               "requested": datetime.now(),
                               }
                    self.memcacheClient.set("job_%d" % job_id, jobDict)
                else:
                    raise Exception("Didn't find max_job_id in namespace %s"
                                    % self.memcacheClient.get_namespace())
            else:
                self.OnRefresh(event, needToValidateSettings=False)

    def OnMyTardis(self, event):
        try:
            import webbrowser
            items = self.foldersView.GetDataViewControl().GetSelections()
            rows = [self.foldersModel.GetRow(item) for item in items]
            if len(rows) == 1:
                folderRecord = self.foldersModel.GetFolderRecord(rows[0])
                if folderRecord.GetDatasetModel() is not None:
                    webbrowser\
                        .open(self.settingsModel.GetMyTardisUrl() + "/" +
                              folderRecord.GetDatasetModel().GetViewUri())
                else:
                    webbrowser.open(self.settingsModel.GetMyTardisUrl())
            else:
                webbrowser.open(self.settingsModel.GetMyTardisUrl())
        except:
            logger.error(traceback.format_exc())

    def OnHelp(self, event):
        new = 2  # Open in a new tab, if possible
        url = "http://mydata.readthedocs.org/en/latest/"
        webbrowser.open(url, new=new)

    def OnWalkthrough(self, event):
        new = 2  # Open in a new tab, if possible
        url = "http://mydata.readthedocs.org/en/latest/macosx-walkthrough.html"
        webbrowser.open(url, new=new)

    def OnAbout(self, event):
        msg = "MyData is a desktop application" \
              " for uploading data to MyTardis " \
              "(https://github.com/mytardis/mytardis).\n\n" \
              "MyData is being developed at the Monash e-Research Centre " \
              "(Monash University, Australia)\n\n" \
              "MyData is open source (GPL3) software available from " \
              "https://github.com/monash-merc/mydata\n\n" \
              "Version:   " + MyDataVersionNumber.versionNumber + "\n" \
              "Commit:  " + CommitDef.LATEST_COMMIT + "\n"
        dlg = wx.MessageDialog(None, msg, "About MyData",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()

    def GetMainFrame(self):
        return self.frame

    def GetMyDataEvents(self):
        return self.myDataEvents

    def GetLastNetworkConnectivityCheckTime(self):
        return self.lastNetworkConnectivityCheckTime

    def SetLastNetworkConnectivityCheckTime(self,
                                            lastNetworkConnectivityCheckTime):
        self.lastNetworkConnectivityCheckTime = \
            lastNetworkConnectivityCheckTime

    def GetLastNetworkConnectivityCheckSuccess(self):
        return self.lastNetworkConnectivityCheckSuccess

    def SetLastNetworkConnectivityCheckSuccess(self, success):
        self.lastNetworkConnectivityCheckSuccess = success

    def GetActiveNetworkInterface(self):
        return self.activeNetworkInterface

    def SetActiveNetworkInterface(self, activeNetworkInterface):
        self.activeNetworkInterface = activeNetworkInterface

    def GetConfigPath(self):
        return self.configPath

    def SetConfigPath(self, configPath):
        self.configPath = configPath


def main(argv):
    app = MyData("MyData")
    app.MainLoop()

if __name__ == "__main__":
    main(sys.argv)
