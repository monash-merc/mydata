import sys
import time
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

from mydata import __version__ as VERSION
from mydata import LATEST_COMMIT
from mydata.views.folders import FoldersView
from mydata.dataviewmodels.folders import FoldersModel
from mydata.controllers.folders import FoldersController
from mydata.views.users import UsersView
from mydata.dataviewmodels.users import UsersModel
from mydata.dataviewmodels.groups import GroupsModel
from mydata.views.verifications import VerificationsView
from mydata.dataviewmodels.verifications import VerificationsModel
from mydata.views.uploads import UploadsView
from mydata.dataviewmodels.uploads import UploadsModel
from models.uploader import UploaderModel
from mydata.views.log import LogView
from models.settings import SettingsModel
from mydata.views.settings import SettingsDialog
from mydata.utils.exceptions import NoActiveNetworkInterface
from mydata.utils.exceptions import InvalidFolderStructure
from mydata.views.statusbar import EnhancedStatusBar
from mydata.logs import logger
from mydata.views.taskbaricon import MyDataTaskBarIcon
from mydata.views.progress import MyDataProgressDialog
import mydata.events as mde
from mydata.media import MyDataIcons
from mydata.media import IconStyle


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
        self.connectedBitmap = MyDataIcons.GetIcon("Connect")
        self.disconnectedBitmap = MyDataIcons.GetIcon("Disconnect")
        self.connected = False
        self.SetConnected(settingsModel.GetMyTardisUrl(), False)

    def OnRefreshIsRunning(self):
        return wx.GetApp().OnRefreshIsRunning()

    def SetOnRefreshRunning(self, onRefreshRunning):
        wx.GetApp().SetOnRefreshRunning(onRefreshRunning)

    def SetStatusMessage(self, msg):
        self.statusbar.SetStatusMessage(msg)

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
        else:
            if sys.platform.startswith("win"):
                self.statusbar.SetStatusConnectionIcon(self.disconnectedBitmap)


class MyData(wx.App):
    def __init__(self, name):
        self.name = name
        wx.App.__init__(self, redirect=False)

    def OnInit(self):
        logger.debug("MyData version:   " + VERSION)
        logger.debug("MyData commit:  " + LATEST_COMMIT)
        appname = "MyData"
        appauthor = "Monash University"
        appdirPath = appdirs.user_data_dir(appname, appauthor)
        logger.debug("appdirPath: " + appdirPath)
        if not os.path.exists(appdirPath):
            os.makedirs(appdirPath)

        self.lastNetworkConnectivityCheckTime = datetime.fromtimestamp(0)
        self.lastNetworkConnectivityCheckSuccess = False
        self.activeNetworkInterface = None

        if hasattr(sys, "frozen"):
            if sys.platform.startswith("darwin"):
                # When frozen with Py2App, the default working directory
                # will be /Applications/MyData.app/Contents/Resources/
                # and setup.py will copy requests's cacert.pem into that
                # directory.
                certPath = os.path.realpath('.')
            else:
                # On Windows, setup.py will install requests's cacert.pem
                # in the same directory as MyData.exe.
                certPath = os.path.dirname(sys.executable)
            os.environ['REQUESTS_CA_BUNDLE'] = \
                os.path.join(certPath, 'cacert.pem')

        # MyData.cfg stores settings in INI format, readable by ConfigParser
        self.SetConfigPath(os.path.join(appdirPath, appname + '.cfg'))
        logger.debug("self.GetConfigPath(): " + self.GetConfigPath())

        self.settingsModel = SettingsModel(self.GetConfigPath())

        parser = argparse.ArgumentParser()
        parser.add_argument("-b", "--background", action="store_true",
                            help="Run non-interactively")
        parser.add_argument("-v", "--version", action="store_true",
                            help="Display MyData version and exit")
        parser.add_argument("-l", "--loglevel", help="set logging verbosity")
        args, unknown = parser.parse_known_args()
        if args.version:
            print "MyData %s (%s)" % (VERSION, LATEST_COMMIT)
            os._exit(0)
        if args.loglevel:
            if args.loglevel == "DEBUG":
                logger.SetLevel(logging.DEBUG)
            elif args.loglevel == "INFO":
                logger.SetLevel(logging.INFO)
            elif args.loglevel == "WARN":
                logger.SetLevel(logging.WARN)
            elif args.loglevel == "ERROR":
                logger.SetLevel(logging.ERROR)
        self.settingsModel.SetBackgroundMode(args.background)

        # Using wx.SingleInstanceChecker to check whether MyData is already
        # running.
        # Running MyData --version is allowed when MyData is already running,
        # in fact this is used by calls to ShellExecuteEx to test user
        # privilege elevation on Windows.
        # A workaround for the 'Deleted stale lock file' issue with
        # SingleInstanceChecker on Mac OS X is to lower the wx logging level.
        # MyData doesn't use wx.Log
        wx.Log.SetLogLevel(wx.LOG_Error)
        self.instance = wx.SingleInstanceChecker(self.name, path=appdirPath)
        if self.instance.IsAnotherRunning():
            wx.MessageBox("MyData is already running!", "MyData",
                          wx.ICON_ERROR)
            return False

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
            self.helpMenu.Append(
                walkthroughMenuItemID, "Mac OS X &Walkthrough")
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
        self.verificationsModel = VerificationsModel()
        self.uploadsModel = UploadsModel()

        self.frame = MyDataFrame(None, -1, self.name,
                                 style=wx.DEFAULT_FRAME_STYLE,
                                 settingsModel=self.settingsModel)
        if sys.platform.startswith("darwin"):
            self.frame.SetMenuBar(self.menuBar)
        self.myDataEvents = mde.MyDataEvents(notifyWindow=self.frame)

        self.onRefreshRunning = False

        self.taskBarIcon = MyDataTaskBarIcon(self.frame, self.settingsModel)

        wx.EVT_TASKBAR_LEFT_UP(self.taskBarIcon, self.OnTaskBarLeftClick)

        self.frame.Bind(wx.EVT_CLOSE, self.OnCloseFrame)
        self.frame.Bind(wx.EVT_ICONIZE, self.OnMinimizeFrame)

        bmp = MyDataIcons.GetIcon("favicon", vendor="MyTardis")
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

        self.frame.Show(True)

        event = None
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

        return True

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
        self.toolbar = self.frame.CreateToolBar()
        self.toolbar.SetToolBitmapSize(wx.Size(24, 24))  # sets icon size

        openIcon = MyDataIcons.GetIcon("Open folder", size="24x24")
        openTool = self.toolbar.AddSimpleTool(wx.ID_ANY, openIcon, "Open",
                                              "Open folder")
        self.Bind(wx.EVT_MENU, self.OnOpen, openTool)

        self.toolbar.AddSeparator()

        refreshIcon = MyDataIcons.GetIcon("Refresh", size="24x24")
        self.refreshTool = self.toolbar.AddSimpleTool(wx.ID_REFRESH,
                                                      refreshIcon,
                                                      "Refresh", "")
        self.toolbar.EnableTool(wx.ID_REFRESH, True)
        self.Bind(wx.EVT_TOOL, self.OnRefresh, self.refreshTool,
                  self.refreshTool.GetId())

        self.toolbar.AddSeparator()

        stopIcon = MyDataIcons.GetIcon("Stop sign", size="24x24",
                                       style=IconStyle.NORMAL)
        self.stopTool = self.toolbar.AddSimpleTool(wx.ID_STOP,
                                                   stopIcon,
                                                   "Stop", "")
        disabledStopIcon = MyDataIcons.GetIcon("Stop sign", size="24x24",
                                               style=IconStyle.DISABLED)
        self.toolbar.SetToolDisabledBitmap(self.stopTool.GetId(),
                                           disabledStopIcon)
        self.toolbar.EnableTool(self.stopTool.GetId(), False)

        self.Bind(wx.EVT_TOOL, self.OnStop, self.stopTool,
                  self.stopTool.GetId())

        self.toolbar.AddSeparator()

        settingsIcon = MyDataIcons.GetIcon("Settings", size="24x24")
        self.settingsTool = self.toolbar.AddSimpleTool(wx.ID_ANY, settingsIcon,
                                                       "Settings", "")
        self.Bind(wx.EVT_TOOL, self.OnSettings, self.settingsTool)

        self.toolbar.AddSeparator()

        internetIcon = MyDataIcons.GetIcon("Internet explorer", size="24x24")
        self.myTardisTool = self.toolbar.AddSimpleTool(wx.ID_ANY, internetIcon,
                                                       "MyTardis", "")
        self.Bind(wx.EVT_TOOL, self.OnMyTardis, self.myTardisTool)

        self.toolbar.AddSeparator()

        aboutIcon = MyDataIcons.GetIcon("About", size="24x24",
                                        style=IconStyle.HOT)
        self.aboutTool = self.toolbar.AddSimpleTool(wx.ID_ANY, aboutIcon,
                                                    "About MyData", "")
        self.Bind(wx.EVT_TOOL, self.OnAbout, self.aboutTool)

        self.toolbar.AddSeparator()

        helpIcon = MyDataIcons.GetIcon("Help", size="24x24",
                                       style=IconStyle.HOT)
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

    def OnRefreshIsRunning(self):
        return self.onRefreshRunning

    def SetOnRefreshRunning(self, onRefreshRunning):
        self.onRefreshRunning = onRefreshRunning

    def OnRefresh(self, event, needToValidateSettings=True):
        shutdownForRefreshAlreadyComplete = False
        if event is None:
            if self.settingsModel.RunningInBackgroundMode():
                logger.debug("OnRefresh called automatically "
                             "from MyData's OnInit().")
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

        if self.OnRefreshIsRunning() and not shutdownForRefreshAlreadyComplete:
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
        self.frame.SetConnected(self.settingsModel.GetMyTardisUrl(),
                                False)
        self.foldersController.SetShuttingDown(False)
        self.SetOnRefreshRunning(True)

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
                                settingsModel=self.settingsModel,
                                nextEvent=settingsValidationForRefreshEvent)
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
                    self.uploaderModel = self.settingsModel.GetUploaderModel()
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
                                self.settingsModel.GetMyTardisUrl(), False)
                        wx.CallAfter(showDialog)
                        return

                    self.settingsValidation = self.settingsModel.Validate()
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

        if "Group" in self.settingsModel.GetFolderStructure():
            self.foldersView.ShowGroupColumn(True)
        else:
            self.foldersView.ShowGroupColumn(False)

        logger.debug("OnRefresh: Creating progress dialog.")

        def cancelCallback():
            def closeProgressDialog():
                self.progressDialog.Show(False)
                # wxMac seems to work better with Destroy here,
                # otherwise sometimes the dialog lingers.
                if sys.platform.startswith("darwin"):
                    self.progressDialog.Destroy()
                    self.progressDialog = None
            wx.CallAfter(closeProgressDialog)
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
        self.progressDialog = \
            MyDataProgressDialog(
                self.frame,
                wx.ID_ANY,
                "MyData Progress",
                "Scanning folders in " +
                self.settingsModel.GetDataDirectory(),
                self.usersModel.GetNumUserOrGroupFolders(),
                userCanAbort=True, cancelCallback=cancelCallback)

        self.numUserFoldersScanned = 0

        def incrementUserFoldersGauge():
            self.numUserFoldersScanned = self.numUserFoldersScanned + 1
            message = "Scanned %d of %d user folders" % (
                self.numUserFoldersScanned,
                self.usersModel.GetNumUserOrGroupFolders())
            self.progressDialog\
                .UpdateUserFoldersGauge(self.numUserFoldersScanned, message)

        # SECTION 4: Start FoldersModel.Refresh(),
        # followed by FoldersController.StartDataUploads().

        def scanDataDirs():
            logger.debug("Starting run() method for thread %s"
                         % threading.current_thread().name)
            wx.CallAfter(self.frame.SetStatusMessage,
                         "Scanning data folders...")
            try:
                self.foldersModel.Refresh(incrementUserFoldersGauge,
                                          self.progressDialog.ShouldAbort)
            except InvalidFolderStructure, ifs:
                # Should not be raised when running in background mode.
                def closeProgressDialog():
                    self.progressDialog.Show(False)
                    # wxMac seems to work better with Destroy here,
                    # otherwise sometimes the dialog lingers.
                    if sys.platform.startswith("darwin"):
                        self.progressDialog.Destroy()
                wx.CallAfter(closeProgressDialog)

                def showMessageDialog():
                    dlg = wx.MessageDialog(None, str(ifs), "MyData",
                                           wx.OK | wx.ICON_ERROR)
                    dlg.ShowModal()
                wx.CallAfter(showMessageDialog)
                self.frame.SetStatusMessage(str(ifs))
                return

            """
            Not closing progress dialog now until the grand shutdown.
            def closeProgressDialog():
                self.progressDialog.Show(False)
                # wxMac seems to work better with Destroy here,
                # otherwise sometimes the dialog lingers.
                if sys.platform.startswith("darwin"):
                    self.progressDialog.Destroy()
            wx.CallAfter(closeProgressDialog)
            """

            def startVerificationsProgressDialog():
                total = self.foldersModel.GetTotalNumFiles()
                self.progressDialog.SetVerificationsRange(total)
                self.progressDialog.UpdateVerificationsGauge(0,
                    "Verified 0 of %d files..."
                    % total)
            wx.CallAfter(startVerificationsProgressDialog)

            def endBusyCursorIfRequired():
                try:
                    wx.EndBusyCursor()
                except wx._core.PyAssertionError, e:
                    if "no matching wxBeginBusyCursor()" not in str(e):
                        logger.error(str(e))
                        raise

            if self.progressDialog.ShouldAbort():
                wx.CallAfter(endBusyCursorIfRequired)
                return

            if self.usersModel.GetNumUserOrGroupFolders() > 0:
                startDataUploadsEvent = \
                    mde.MyDataEvent(mde.EVT_START_DATA_UPLOADS,
                                    foldersController=self.foldersController)
                logger.debug("Posting startDataUploadsEvent")
                wx.PostEvent(wx.GetApp().GetMainFrame(),
                             startDataUploadsEvent)
            else:
                message = "No user/group folders to upload from."
                logger.debug(message)
                self.frame.SetStatusMessage(message)

            wx.CallAfter(endBusyCursorIfRequired)
            logger.debug("Finishing run() method for thread %s"
                         % threading.current_thread().name)

        thread = threading.Thread(target=scanDataDirs,
                                  name="ScanDataDirectoriesThread")
        logger.debug("OnRefresh: Starting scanDataDirs thread.")
        thread.start()
        logger.debug("OnRefresh: Started scanDataDirs thread.")

    def UpdateVerificationsProgressDialog(self):
        if not self.progressDialog:
            return
        total = self.foldersModel.GetTotalNumFiles()
        numVerificationsCompleted = self.verificationsModel.GetCompletedCount()
        message = "Verified %d of %d files..." \
            % (numVerificationsCompleted, total)
        self.progressDialog.UpdateVerificationsGauge(numVerificationsCompleted, message)

    def UpdateUploadsProgressDialog(self):
        if not self.progressDialog:
            return
        total = self.uploadsModel.GetRowCount()
        numUploadsCompleted = self.uploadsModel.GetCompletedCount()
        message = "Uploaded %d of %d files..." \
            % (numUploadsCompleted, total)
        self.progressDialog.SetUploadsRange(total)
        self.progressDialog.UpdateUploadsGauge(numUploadsCompleted, message)

    def OnStop(self, event):
        self.uploadsView.OnCancelRemainingUploads(event)

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
              "Version:   " + VERSION + "\n" \
              "Commit:  " + LATEST_COMMIT + "\n"
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
    print "Please use run.py in MyData.py's parent directory instead."
