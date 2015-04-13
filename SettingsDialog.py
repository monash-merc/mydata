import wx
import wx.aui
import wx.lib.masked
import re
import requests
import threading
from datetime import datetime
import sys
import os
import traceback

from logger.Logger import logger
from SettingsModel import SettingsModel
from Exceptions import DuplicateKey
from Exceptions import IncompatibleMyTardisVersion
import MyDataEvents as mde
from DragAndDrop import MyDataSettingsDropTarget


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, ID, title,
                 settingsModel,
                 size=wx.DefaultSize,
                 pos=wx.DefaultPosition,
                 style=wx.DEFAULT_DIALOG_STYLE):
        wx.Dialog.__init__(self, parent, ID, title=title, size=size, pos=pos,
                           style=style)

        self.CenterOnParent()

        self.parent = parent
        self.settingsModel = settingsModel

        self.SetDropTarget(MyDataSettingsDropTarget(self))

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.dialogPanel = wx.Panel(self)

        self.settingsTabsNotebook = \
            wx.aui.AuiNotebook(self.dialogPanel, style=wx.aui.AUI_NB_TOP)
        self.generalPanel = wx.Panel(self.settingsTabsNotebook)
        self.schedulePanel = wx.Panel(self.settingsTabsNotebook)
        self.advancedPanel = wx.Panel(self.settingsTabsNotebook)

        self.dialogPanelSizer = wx.BoxSizer()
        self.dialogPanelSizer.Add(self.settingsTabsNotebook, 0,
                                  wx.EXPAND | wx.ALL, 5)
        self.dialogPanel.SetSizer(self.dialogPanelSizer)

        sizer.Add(self.dialogPanel, 1, wx.EXPAND | wx.ALL, 5)

        # General tab

        self.generalPanelSizer = wx.FlexGridSizer(rows=11, cols=3,
                                                  vgap=5, hgap=5)
        self.generalPanel.SetSizer(self.generalPanelSizer)
        self.generalPanelSizer.AddGrowableCol(1)

        # Add blank space above the settings fields. Our FlexGridSizer
        # has 3 columns, so we'll add 3 units of blank space.  We don't
        # care about the width (so we use -1), but we choose a height of
        # 5px (plus the FlexGridSizer's default vgap).
        self.generalPanelSizer.Add(wx.Size(-1, 5))
        self.generalPanelSizer.Add(wx.Size(-1, 5))
        self.generalPanelSizer.Add(wx.Size(-1, 5))

        self.instrumentNameLabel = wx.StaticText(self.generalPanel, wx.ID_ANY,
                                                 "Instrument Name:")
        self.generalPanelSizer.Add(self.instrumentNameLabel,
                                   flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.instrumentNameField = wx.TextCtrl(self.generalPanel,
                                               wx.ID_ANY, "")
        if sys.platform.startswith("darwin"):
            self.instrumentNameField.SetMinSize(wx.Size(290, -1))
        else:
            self.instrumentNameField.SetMinSize(wx.Size(265, -1))
        self.generalPanelSizer.Add(self.instrumentNameField,
                                   flag=wx.EXPAND | wx.ALL, border=5)
        blankLine = wx.StaticText(self.generalPanel, wx.ID_ANY, "")
        self.generalPanelSizer.Add(blankLine)

        self.facilityNameLabel = wx.StaticText(self.generalPanel, wx.ID_ANY,
                                               "Facility Name:")
        self.generalPanelSizer.Add(self.facilityNameLabel,
                                   flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.facilityNameField = wx.TextCtrl(self.generalPanel, wx.ID_ANY, "")
        self.generalPanelSizer.Add(self.facilityNameField,
                                   flag=wx.EXPAND | wx.ALL, border=5)
        blankLine = wx.StaticText(self.generalPanel, wx.ID_ANY, "")
        self.generalPanelSizer.Add(blankLine)

        self.contactNameLabel = wx.StaticText(self.generalPanel, wx.ID_ANY,
                                              "Contact Name:")
        self.generalPanelSizer.Add(self.contactNameLabel,
                                   flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.contactNameField = wx.TextCtrl(self.generalPanel, wx.ID_ANY,
                                            "")
        self.generalPanelSizer.Add(self.contactNameField,
                                   flag=wx.EXPAND | wx.ALL, border=5)
        self.generalPanelSizer.Add(wx.StaticText(self.generalPanel, wx.ID_ANY,
                                                 ""))

        self.contactEmailLabel = wx.StaticText(self.generalPanel, wx.ID_ANY,
                                               "Contact Email:")
        self.generalPanelSizer.Add(self.contactEmailLabel,
                                   flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.contactEmailField = wx.TextCtrl(self.generalPanel, wx.ID_ANY,
                                             "")
        self.generalPanelSizer.Add(self.contactEmailField,
                                   flag=wx.EXPAND | wx.ALL, border=5)
        self.generalPanelSizer.Add(wx.StaticText(self.generalPanel, wx.ID_ANY,
                                                 ""))

        self.dataDirectoryLabel = wx.StaticText(self.generalPanel, wx.ID_ANY,
                                                "Data Directory:")
        self.generalPanelSizer.Add(self.dataDirectoryLabel,
                                   flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.dataDirectoryField = wx.TextCtrl(self.generalPanel, wx.ID_ANY, "")
        self.generalPanelSizer.Add(self.dataDirectoryField,
                                   flag=wx.EXPAND | wx.ALL, border=5)
        self.browseDataDirectoryButton = wx.Button(self.generalPanel,
                                                   wx.ID_ANY, "Browse...")
        self.Bind(wx.EVT_BUTTON, self.OnBrowse, self.browseDataDirectoryButton)
        self.generalPanelSizer.Add(self.browseDataDirectoryButton,
                                   flag=wx.EXPAND | wx.ALL, border=5)

        self.myTardisUrlLabel = wx.StaticText(self.generalPanel, wx.ID_ANY,
                                              "MyTardis URL:")
        self.generalPanelSizer.Add(self.myTardisUrlLabel,
                                   flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.myTardisUrlField = wx.TextCtrl(self.generalPanel, wx.ID_ANY, "")
        self.generalPanelSizer.Add(self.myTardisUrlField,
                                   flag=wx.EXPAND | wx.ALL, border=5)
        self.generalPanelSizer.Add(wx.StaticText(self.generalPanel, wx.ID_ANY,
                                                 ""))

        usernameLabel = wx.StaticText(self.generalPanel, wx.ID_ANY,
                                      "MyTardis Username:")
        self.generalPanelSizer.Add(usernameLabel,
                                   flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.usernameField = wx.TextCtrl(self.generalPanel, wx.ID_ANY, "")
        self.generalPanelSizer.Add(self.usernameField,
                                   flag=wx.EXPAND | wx.ALL, border=5)
        self.generalPanelSizer.Add(wx.StaticText(self.generalPanel, wx.ID_ANY,
                                                 ""))

        apiKeyLabel = wx.StaticText(self.generalPanel, wx.ID_ANY,
                                    "MyTardis API Key:")
        self.generalPanelSizer.Add(apiKeyLabel, flag=wx.ALIGN_RIGHT | wx.ALL,
                                   border=5)
        self.apiKeyField = wx.TextCtrl(self.generalPanel, wx.ID_ANY, "",
                                       style=wx.TE_PASSWORD)

        # For security reasons, Mac OS X tries to disable copy/paste etc.
        # in password fields.  Copy and Cut are genuine security risks,
        # but we can re-enable paste and select all.  We make up new IDs,
        # rather than using self.apiKeyField.GetId(), so that the OS
        # doesn't try to impose its security rules on our "password" field.
        pasteId = wx.NewId()
        selectAllId = wx.NewId()
        saveId = wx.NewId()
        acceleratorList = \
            [(wx.ACCEL_CTRL, ord('V'), pasteId),
             (wx.ACCEL_CTRL, ord('A'), selectAllId),
             (wx.ACCEL_CTRL, ord('S'), saveId)]
        self.Bind(wx.EVT_MENU, self.OnPaste, id=pasteId)
        self.Bind(wx.EVT_MENU, self.OnSelectAll, id=selectAllId)
        self.Bind(wx.EVT_MENU, self.OnSave, id=saveId)
        acceleratorTable = wx.AcceleratorTable(acceleratorList)
        self.SetAcceleratorTable(acceleratorTable)

        self.Bind(wx.EVT_SET_FOCUS, self.OnApiKeyFieldFocused,
                  self.apiKeyField)

        self.generalPanelSizer.Add(self.apiKeyField, flag=wx.EXPAND | wx.ALL,
                                   border=5)
        self.generalPanelSizer.Add(wx.StaticText(self.generalPanel, wx.ID_ANY,
                                                 ""))
        # Add blank space above the settings fields. Our FlexGridSizer
        # has 3 columns, so we'll add 3 units of blank space.  We don't
        # care about the width (so we use -1), but we choose a height of
        # 5px (plus the FlexGridSizer's default vgap).
        self.generalPanelSizer.Add(wx.Size(-1, 5))
        self.generalPanelSizer.Add(wx.Size(-1, 5))
        self.generalPanelSizer.Add(wx.Size(-1, 5))

        self.generalPanel.Fit()
        generalPanelSize = self.generalPanel.GetSize()
        self.settingsTabsNotebook.AddPage(self.generalPanel, "General")

        # Schedule tab

        print "TO DO: Implement scheduling functionality configured " \
                "by these fields."

        self.innerSchedulePanel = wx.Panel(self.schedulePanel)
        self.innerSchedulePanelSizer = wx.BoxSizer(wx.VERTICAL)

        self.scheduleTypePanel = wx.Panel(self.innerSchedulePanel)
        self.scheduleTypePanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.scheduleTypePanelSizer.Add(wx.StaticText(self.innerSchedulePanel,
                                                      wx.ID_ANY,
                                                      "Schedule type"))

        choices = ["Once", "Daily", "Weekly", "Timer", "Manually",
                   "On startup"]
        self.scheduleTypeComboBox = wx.ComboBox(self.scheduleTypePanel,
                                                choices=choices,
                                                style=wx.CB_READONLY)
        self.scheduleTypeComboBox.SetMinSize((150, -1))
        self.scheduleTypeComboBox.SetSelection(0)
        self.scheduleTypePanelSizer.Add(self.scheduleTypeComboBox)
        self.Bind(wx.EVT_COMBOBOX, self.OnScheduleTypeChange,
                  self.scheduleTypeComboBox)
        self.scheduleTypePanel.SetSizerAndFit(self.scheduleTypePanelSizer)
        self.innerSchedulePanelSizer.Add(self.scheduleTypePanel)
        self.innerSchedulePanelSizer.AddSpacer(10)

        self.daysOfTheWeekPanel = wx.Panel(self.innerSchedulePanel, wx.ID_ANY)
        self.dateTimeGroupBox = wx.StaticBox(self.daysOfTheWeekPanel,
                                             wx.ID_ANY,
                                             label="Days of the week")
        # self.dateTimeGroupBox.SetFont(self.smallFont)
        self.daysOfTheWeekGroupBoxSizer = \
            wx.StaticBoxSizer(self.dateTimeGroupBox, wx.VERTICAL)
        self.daysOfTheWeekPanel.SetSizer(self.daysOfTheWeekGroupBoxSizer)
        self.innerDaysOfTheWeekPanel = wx.Panel(self.daysOfTheWeekPanel,
                                                wx.ID_ANY)
        self.innerDaysOfTheWeekPanelSizer = wx.FlexGridSizer(rows=2, cols=5,
                                                             hgap=10, vgap=10)
        self.innerDaysOfTheWeekPanel\
            .SetSizer(self.innerDaysOfTheWeekPanelSizer)

        self.mondayCheckBox = wx.CheckBox(self.innerDaysOfTheWeekPanel,
                                          label="Monday")
        self.innerDaysOfTheWeekPanelSizer.Add(self.mondayCheckBox)
        self.tuesdayCheckBox = wx.CheckBox(self.innerDaysOfTheWeekPanel,
                                           label="Tuesday")
        self.innerDaysOfTheWeekPanelSizer.Add(self.tuesdayCheckBox)
        self.wednesdayCheckBox = wx.CheckBox(self.innerDaysOfTheWeekPanel,
                                             label="Wednesday")
        self.innerDaysOfTheWeekPanelSizer.Add(self.wednesdayCheckBox)
        self.thursdayCheckBox = wx.CheckBox(self.innerDaysOfTheWeekPanel,
                                            label="Thursday")
        self.innerDaysOfTheWeekPanelSizer.Add(self.thursdayCheckBox)
        self.fridayCheckBox = wx.CheckBox(self.innerDaysOfTheWeekPanel,
                                          label="Friday")
        self.innerDaysOfTheWeekPanelSizer.Add(self.fridayCheckBox)
        self.saturdayCheckBox = wx.CheckBox(self.innerDaysOfTheWeekPanel,
                                            label="Saturday")
        self.innerDaysOfTheWeekPanelSizer.Add(self.saturdayCheckBox)
        self.sundayCheckBox = wx.CheckBox(self.innerDaysOfTheWeekPanel,
                                          label="Sunday")
        self.innerDaysOfTheWeekPanelSizer.Add(self.sundayCheckBox)

        self.innerDaysOfTheWeekPanel\
            .SetSizerAndFit(self.innerDaysOfTheWeekPanelSizer)
        self.daysOfTheWeekGroupBoxSizer.Add(self.innerDaysOfTheWeekPanel,
                                            flag=wx.EXPAND)
        self.daysOfTheWeekPanel.SetSizerAndFit(self.daysOfTheWeekGroupBoxSizer)
        self.innerSchedulePanelSizer.Add(self.daysOfTheWeekPanel,
                                         flag=wx.EXPAND)
        self.innerSchedulePanelSizer.AddSpacer(10)

        self.dateTimePanel = wx.Panel(self.innerSchedulePanel, wx.ID_ANY)
        self.innerSchedulePanelSizer.Add(self.dateTimePanel, flag=wx.EXPAND)
        self.dateTimeGroupBox = wx.StaticBox(self.dateTimePanel, wx.ID_ANY,
                                             label="Date/Time")
        # self.dateTimeGroupBox.SetFont(self.smallFont)
        self.dateTimeGroupBoxSizer = wx.StaticBoxSizer(self.dateTimeGroupBox,
                                                       wx.VERTICAL)
        self.dateTimePanel.SetSizer(self.dateTimeGroupBoxSizer)
        self.innerDateTimePanel = wx.Panel(self.dateTimePanel, wx.ID_ANY)
        self.innerDateTimePanelSizer = wx.FlexGridSizer(rows=2, cols=2,
                                                        hgap=10, vgap=10)
        self.innerDateTimePanel.SetSizer(self.innerDateTimePanelSizer)

        self.innerDateTimePanel.SetSizerAndFit(self.innerDateTimePanelSizer)
        self.dateTimeGroupBoxSizer.Add(self.innerDateTimePanel, flag=wx.EXPAND)
        self.dateTimePanel.SetSizerAndFit(self.dateTimeGroupBoxSizer)
        self.datePanel = wx.Panel(self.innerDateTimePanel, wx.ID_ANY)
        self.datePanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.dateLabel = wx.StaticText(self.datePanel, label="Date")
        self.datePanelSizer.Add(self.dateLabel)
        # self.dateLabel.SetFont(self.smallFont)
        self.dateCtrl = wx.DatePickerCtrl(self.datePanel, size=(120, -1),
                                          style=wx.DP_DROPDOWN)
        self.datePanelSizer.Add(self.dateCtrl)
        self.datePanel.SetSizerAndFit(self.datePanelSizer)
        self.innerDateTimePanelSizer.Add(self.datePanel)

        self.timePanel = wx.Panel(self.innerDateTimePanel, wx.ID_ANY)
        self.timePanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.timeLabel = wx.StaticText(self.timePanel, label="Time")
        self.timePanelSizer.Add(self.timeLabel)
        # self.timeLabel.SetFont(self.smallFont)
        self.timeEntryPanel = wx.Panel(self.timePanel, wx.ID_ANY)
        self.timeEntryPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.timeCtrl = wx.lib.masked.TimeCtrl(self.timeEntryPanel,
                                               displaySeconds=False,
                                               size=(120, -1))
        self.timeEntryPanelSizer.Add(self.timeCtrl)
        height = self.timeCtrl.GetSize().height
        self.timeSpin = wx.SpinButton(self.timeEntryPanel, wx.ID_ANY,
                                      size=(-1, height), style=wx.SP_VERTICAL)
        self.timeCtrl.BindSpinButton(self.timeSpin)
        self.timeEntryPanelSizer.Add(self.timeSpin)
        self.timeEntryPanel.SetSizerAndFit(self.timeEntryPanelSizer)
        self.timePanelSizer.Add(self.timeEntryPanel)
        self.timePanel.SetSizerAndFit(self.timePanelSizer)
        self.innerDateTimePanelSizer.Add(self.timePanel)

        self.timerPanel = wx.Panel(self.innerDateTimePanel, wx.ID_ANY)
        self.timerPanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.timerLabel = wx.StaticText(self.timerPanel,
                                        label="Timer (minutes)")
        self.timerPanelSizer.Add(self.timerLabel)
        # self.timerLabel.SetFont(self.smallFont)
        self.timerEntryPanel = wx.Panel(self.timerPanel, wx.ID_ANY)
        self.timerEntryPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.timerNumCtrl = wx.lib.masked.NumCtrl(self.timerEntryPanel,
                                                  size=(120, -1))
        self.timerNumCtrl.SetMax(999)
        self.timerNumCtrl.SetValue(180)
        self.timerEntryPanelSizer.Add(self.timerNumCtrl)
        height = self.timerNumCtrl.GetSize().height
        self.timerSpin = wx.SpinButton(self.timerEntryPanel, wx.ID_ANY,
                                       size=(-1, height), style=wx.SP_VERTICAL)
        self.timerSpin.SetMax(999)
        self.timerSpin.SetValue(180)
        self.Bind(wx.EVT_SPIN, self.OnSpinTimer, self.timerSpin)
        self.timerEntryPanelSizer.Add(self.timerSpin)
        self.timerEntryPanel.SetSizerAndFit(self.timerEntryPanelSizer)
        self.timerPanelSizer.Add(self.timerEntryPanel)
        self.timerPanel.SetSizerAndFit(self.timerPanelSizer)
        self.innerDateTimePanelSizer.Add(self.timerPanel)

        self.fromToPanel = wx.Panel(self.innerDateTimePanel, wx.ID_ANY)
        self.fromToPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.fromPanel = wx.Panel(self.fromToPanel, wx.ID_ANY)
        self.fromPanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.fromLabel = wx.StaticText(self.fromPanel, label="From:")
        self.fromPanelSizer.Add(self.fromLabel)
        # self.fromLabel.SetFont(self.smallFont)
        self.fromTimeEntryPanel = wx.Panel(self.fromPanel, wx.ID_ANY)
        self.fromTimeEntryPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.fromTimeCtrl = wx.lib.masked.TimeCtrl(self.fromTimeEntryPanel,
                                                   displaySeconds=False,
                                                   size=(120, -1))
        self.fromTimeEntryPanelSizer.Add(self.fromTimeCtrl)
        height = self.fromTimeCtrl.GetSize().height
        self.fromTimeSpin = wx.SpinButton(self.fromTimeEntryPanel, wx.ID_ANY,
                                          size=(-1, height),
                                          style=wx.SP_VERTICAL)
        self.fromTimeCtrl.BindSpinButton(self.fromTimeSpin)
        self.fromTimeEntryPanelSizer.Add(self.fromTimeSpin)
        self.fromTimeEntryPanel.SetSizerAndFit(self.fromTimeEntryPanelSizer)
        self.fromPanelSizer.Add(self.fromTimeEntryPanel)
        self.fromPanel.SetSizerAndFit(self.fromPanelSizer)
        self.fromToPanelSizer.Add(self.fromPanel)
        self.fromToPanelSizer.AddSpacer(10)
        self.toPanel = wx.Panel(self.fromToPanel, wx.ID_ANY)
        self.toPanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.toLabel = wx.StaticText(self.toPanel, label="To:")
        self.toPanelSizer.Add(self.toLabel)
        # self.toLabel.SetFont(self.smallFont)
        self.toTimeEntryPanel = wx.Panel(self.toPanel, wx.ID_ANY)
        self.toTimeEntryPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.toTimeCtrl = wx.lib.masked.TimeCtrl(self.toTimeEntryPanel,
                                                 displaySeconds=False,
                                                 value='23:59:59',
                                                 size=(120, -1))
        self.toTimeEntryPanelSizer.Add(self.toTimeCtrl)
        height = self.toTimeCtrl.GetSize().height
        self.fromTimeSpin = wx.SpinButton(self.toTimeEntryPanel, wx.ID_ANY,
                                          size=(-1, height),
                                          style=wx.SP_VERTICAL)
        self.toTimeCtrl.BindSpinButton(self.fromTimeSpin)
        self.toTimeEntryPanelSizer.Add(self.fromTimeSpin)
        self.toTimeEntryPanel.SetSizerAndFit(self.toTimeEntryPanelSizer)
        self.toPanelSizer.Add(self.toTimeEntryPanel)
        self.toPanel.SetSizerAndFit(self.toPanelSizer)
        self.fromToPanelSizer.Add(self.toPanel)
        self.fromToPanel.SetSizerAndFit(self.fromToPanelSizer)
        self.innerDateTimePanelSizer.Add(self.fromToPanel)

        self.innerDateTimePanel.SetSizerAndFit(self.innerDateTimePanelSizer)
        self.dateTimePanel.SetSizerAndFit(self.dateTimeGroupBoxSizer)

        self.innerSchedulePanel.SetSizerAndFit(self.innerSchedulePanelSizer)

        schedulePanelSizer = wx.FlexGridSizer(rows=1, cols=1)
        schedulePanelSizer.Add(self.innerSchedulePanel,
                               flag=wx.ALL, border=20)
        self.schedulePanel.SetSizerAndFit(schedulePanelSizer)

        self.OnScheduleTypeChange(None)

        self.settingsTabsNotebook.AddPage(self.schedulePanel, "Schedule")

        # Advanced tab

        self.advancedPanelSizer = wx.FlexGridSizer(rows=7, cols=3,
                                                   vgap=5, hgap=5)
        self.advancedPanel.SetSizer(self.advancedPanelSizer)
        # self.advancedPanelSizer.AddGrowableCol(1)

        # Add blank space above the settings fields. Our FlexGridSizer
        # has 4 columns, so we'll add 4 units of blank space.  We don't
        # care about the width (so we use -1), but we choose a height of
        # 5px (plus the FlexGridSizer's default vgap).
        self.advancedPanelSizer.Add(wx.Size(-1, 5))
        self.advancedPanelSizer.Add(wx.Size(-1, 5))
        self.advancedPanelSizer.Add(wx.Size(-1, 5))

        folderStructureLabel = wx.StaticText(self.advancedPanel, wx.ID_ANY,
                                             "Folder Structure:")
        self.advancedPanelSizer.Add(folderStructureLabel,
                                    flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.folderStructures = [
            'Username / Dataset',
            'Email / Dataset',
            'Username / Experiment / Dataset',
            'Email / Experiment / Dataset',
            'Username / "MyTardis" / Experiment / Dataset',
            'User Group / Instrument / Full Name / Dataset']
        self.folderStructureComboBox = \
            wx.ComboBox(self.advancedPanel, wx.ID_ANY,
                        choices=self.folderStructures, style=wx.CB_READONLY)
        self.Bind(wx.EVT_COMBOBOX, self.OnSelectFolderStructure,
                  self.folderStructureComboBox)
        self.folderStructureComboBox.SetValue("Username / Dataset")
        self.advancedPanelSizer.Add(self.folderStructureComboBox,
                                    flag=wx.EXPAND | wx.ALL, border=5)
        self.advancedPanelSizer.Add(wx.StaticText(self.advancedPanel,
                                                  wx.ID_ANY, ""))

        checkForMissingFoldersLabel = \
            wx.StaticText(self.advancedPanel, wx.ID_ANY,
                          "Check for missing folders:")
        self.advancedPanelSizer.Add(checkForMissingFoldersLabel,
                                    flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.checkForMissingFoldersCheckBox = \
            wx.CheckBox(self.advancedPanel, wx.ID_ANY, "")
        self.advancedPanelSizer\
            .Add(self.checkForMissingFoldersCheckBox,
                 flag=wx.EXPAND | wx.ALL, border=5)
        self.advancedPanelSizer.Add(wx.StaticText(self.advancedPanel,
                                                  wx.ID_ANY, ""))

        datasetGroupingLabel = wx.StaticText(self.advancedPanel, wx.ID_ANY,
                                             "Experiment (Dataset Grouping):")
        self.advancedPanelSizer.Add(datasetGroupingLabel,
                                    flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.datasetGroupingField = wx.TextCtrl(self.advancedPanel,
                                                wx.ID_ANY, "")
        self.datasetGroupingField\
            .SetValue("Instrument Name - Data Owner's Full Name")
        self.datasetGroupingField.SetEditable(False)
        self.advancedPanelSizer.Add(self.datasetGroupingField,
                                    flag=wx.EXPAND | wx.ALL, border=5)
        self.advancedPanelSizer.Add(wx.StaticText(self.advancedPanel,
                                                  wx.ID_ANY, "        "))

        self.groupPrefixLabel = wx.StaticText(self.advancedPanel, wx.ID_ANY,
                                              "User Group Prefix:")
        self.advancedPanelSizer.Add(self.groupPrefixLabel,
                                    flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.groupPrefixField = wx.TextCtrl(self.advancedPanel, wx.ID_ANY, "")
        self.advancedPanelSizer.Add(self.groupPrefixField,
                                    flag=wx.EXPAND | wx.ALL, border=5)
        self.advancedPanelSizer.Add(wx.StaticText(self.advancedPanel,
                                                  wx.ID_ANY, ""))

        self.ignoreDatasetsOlderThanCheckBox = \
            wx.CheckBox(self.advancedPanel, wx.ID_ANY,
                        "Ignore datasets older than:")
        self.Bind(wx.EVT_CHECKBOX, self.OnIgnoreOldDatasetsCheckBox,
                  self.ignoreDatasetsOlderThanCheckBox)
        self.advancedPanelSizer.Add(self.ignoreDatasetsOlderThanCheckBox,
                                    flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.ignoreIntervalPanel = wx.Panel(self.advancedPanel)
        self.ignoreIntervalPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.ignoreIntervalPanel.SetSizer(self.ignoreIntervalPanelSizer)

        self.ignoreDatasetsOlderThanSpinCtrl = \
            wx.SpinCtrl(self.ignoreIntervalPanel, wx.ID_ANY,
                        "999", min=0, max=999)
        self.Bind(wx.EVT_SPINCTRL, self.OnIgnoreOldDatasetsSpinCtrl,
                  self.ignoreDatasetsOlderThanSpinCtrl)
        self.ignoreDatasetsOlderThanSpinCtrl.Enable(False)
        self.ignoreIntervalPanelSizer.Add(self.ignoreDatasetsOlderThanSpinCtrl,
                                          flag=wx.EXPAND | wx.ALL, border=5)
        self.intervalUnitsPlural = ['days', 'weeks', 'months', 'years']
        self.intervalUnitsSingular = ['day', 'week', 'month', 'year']
        self.showingSingularUnits = False
        self.intervalUnitsComboBox = \
            wx.ComboBox(self.ignoreIntervalPanel, wx.ID_ANY,
                        choices=self.intervalUnitsPlural, style=wx.CB_READONLY)
        self.intervalUnitsComboBox.Enable(False)
        self.ignoreIntervalPanelSizer.Add(self.intervalUnitsComboBox,
                                          flag=wx.EXPAND | wx.ALL, border=5)

        self.advancedPanelSizer.Add(self.ignoreIntervalPanel, flag=wx.EXPAND,
                                    border=5)
        self.advancedPanelSizer.Add(wx.StaticText(self.advancedPanel,
                                                  wx.ID_ANY, ""))

        maxUploadThreadsLabel = wx.StaticText(self.advancedPanel, wx.ID_ANY,
                                              "Maximum # of upload threads:")
        self.advancedPanelSizer.Add(maxUploadThreadsLabel,
                                    flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.maxUploadThreadsPanel = wx.Panel(self.advancedPanel)
        self.maxUploadThreadsPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.maxUploadThreadsPanel.SetSizer(self.maxUploadThreadsPanelSizer)

        self.maximumUploadThreadsSpinCtrl = \
            wx.SpinCtrl(self.maxUploadThreadsPanel, wx.ID_ANY,
                        "5", min=1, max=99)
        self.maxUploadThreadsPanelSizer.Add(self.maximumUploadThreadsSpinCtrl,
                                            flag=wx.EXPAND | wx.ALL, border=5)
        self.advancedPanelSizer.Add(self.maxUploadThreadsPanel,
                                    flag=wx.EXPAND, border=5)

        self.advancedPanel.Fit()
        self.settingsTabsNotebook.AddPage(self.advancedPanel, "Advanced")

        self.settingsTabsNotebook.Fit()
        self.settingsTabsNotebook\
            .SetMinSize(wx.Size(generalPanelSize.GetWidth(),
                                generalPanelSize.height +
                                self.settingsTabsNotebook.GetTabCtrlHeight()))
        self.dialogPanel.Fit()

        line = wx.StaticLine(self, wx.ID_ANY, size=(20, -1),
                             style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.EXPAND | wx.RIGHT | wx.TOP, 5)

        buttonSizer = wx.StdDialogButtonSizer()

        self.okButton = wx.Button(self, wx.ID_OK, "OK")
        self.okButton.SetDefault()
        buttonSizer.AddButton(self.okButton)

        self.helpButton = wx.Button(self, wx.ID_HELP, "Help")
        buttonSizer.AddButton(self.helpButton)

        # We need to use one of the standard IDs recognized by
        # StdDialogSizer:
        self.lockOrUnlockButton = wx.Button(self, wx.ID_APPLY, "Lock")
        buttonSizer.AddButton(self.lockOrUnlockButton)
        self.Bind(wx.EVT_BUTTON, self.OnLockOrUnlockSettings,
                  self.lockOrUnlockButton)

        self.cancelButton = wx.Button(self, wx.ID_CANCEL, "Cancel")
        buttonSizer.AddButton(self.cancelButton)
        buttonSizer.Realize()
        # Using wx.ID_CANCEL makes command-c cancel on Mac OS X,
        # but we want to use command-c for copying to the clipboard.
        # We set the ID to wx.ID_CANCEL earlier to help
        # wx.StdDialogButtonSizer to lay out the buttons correctly.
        self.cancelButton.SetId(wx.NewId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self.cancelButton)
        # As with the Cancel button, we set the OK button's ID to
        # wx.ID_OK initially to help wx.StdDialogButtonSizer to
        # lay out the buttons.  But at least on Mac OS X, I don't
        # trust the event handling to work correctly, so I'm
        # changing the button's ID here:
        self.okButton.SetId(wx.NewId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, self.okButton)
        self.helpButton.SetId(wx.NewId())
        self.Bind(wx.EVT_BUTTON, self.OnHelp, self.helpButton)

        sizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        self.SetSizer(sizer)
        self.Fit()

        self.UpdateFieldsFromModel(self.settingsModel)

        folderStructure = self.folderStructureComboBox.GetValue()
        if folderStructure != \
                'User Group / Instrument / Full Name / Dataset':
            self.groupPrefixLabel.Show(False)
            self.groupPrefixField.Show(False)

    def GetInstrumentName(self):
        return self.instrumentNameField.GetValue()

    def SetInstrumentName(self, instrumentName):
        self.instrumentNameField.SetValue(instrumentName)

    def GetFacilityName(self):
        return self.facilityNameField.GetValue()

    def SetFacilityName(self, instrumentName):
        self.facilityNameField.SetValue(instrumentName)

    def GetMyTardisUrl(self):
        return self.myTardisUrlField.GetValue()

    def GetContactName(self):
        return self.contactNameField.GetValue()

    def SetContactName(self, contactName):
        self.contactNameField.SetValue(contactName)

    def GetContactEmail(self):
        return self.contactEmailField.GetValue()

    def SetContactEmail(self, contactEmail):
        self.contactEmailField.SetValue(contactEmail)

    def GetDataDirectory(self):
        return self.dataDirectoryField.GetValue()

    def SetDataDirectory(self, dataDirectory):
        self.dataDirectoryField.SetValue(dataDirectory)

    def SetMyTardisUrl(self, myTardisUrl):
        self.myTardisUrlField.SetValue(myTardisUrl)

    def GetUsername(self):
        return self.usernameField.GetValue()

    def SetUsername(self, username):
        self.usernameField.SetValue(username)

    def GetApiKey(self):
        return self.apiKeyField.GetValue()

    def SetApiKey(self, apiKey):
        self.apiKeyField.SetValue(apiKey)

    def GetFolderStructure(self):
        return self.folderStructureComboBox.GetValue()

    def SetFolderStructure(self, folderStructure):
        self.folderStructureComboBox.SetValue(folderStructure)

    def GetDatasetGrouping(self):
        return self.datasetGroupingField.GetValue()

    def SetDatasetGrouping(self, datasetGrouping):
        self.datasetGroupingField.SetValue(datasetGrouping)

    def GetGroupPrefix(self):
        return self.groupPrefixField.GetValue()

    def SetGroupPrefix(self, groupPrefix):
        self.groupPrefixField.SetValue(groupPrefix)

    def CheckForMissingFolders(self):
        return self.checkForMissingFoldersCheckBox.GetValue()

    def SetCheckForMissingFolders(self, checkForMissingFolders):
        self.checkForMissingFoldersCheckBox.SetValue(checkForMissingFolders)

    def IgnoreOldDatasets(self):
        return self.ignoreDatasetsOlderThanCheckBox.GetValue()

    def SetIgnoreOldDatasets(self, ignoreOldDatasets):
        self.ignoreDatasetsOlderThanCheckBox.SetValue(ignoreOldDatasets)

    def GetIgnoreOldDatasetIntervalNumber(self):
        return self.ignoreDatasetsOlderThanSpinCtrl.GetValue()

    def SetIgnoreOldDatasetIntervalNumber(self,
                                          ignoreOldDatasetIntervalNumber):
        self.ignoreDatasetsOlderThanSpinCtrl\
            .SetValue(ignoreOldDatasetIntervalNumber)

    def GetIgnoreOldDatasetIntervalUnit(self):
        return self.intervalUnitsComboBox.GetValue()

    def SetIgnoreOldDatasetIntervalUnit(self, ignoreOldDatasetIntervalUnit):
        self.intervalUnitsComboBox.SetValue(ignoreOldDatasetIntervalUnit)

    def GetMaxUploadThreads(self):
        return self.maximumUploadThreadsSpinCtrl.GetValue()

    def SetMaxUploadThreads(self, numberOfThreads):
        self.maximumUploadThreadsSpinCtrl.SetValue(numberOfThreads)

    def Locked(self):
        return self.lockOrUnlockButton.GetLabel() == "Unlock"

    def SetLocked(self, locked):
        """
        When SettingsDialog is first displayed, it is in the unlocked
        state, so the button label says "Lock" (allowing the user to
        switch to the locked state).  When MyData reads the saved
        settings from disk, if it finds that settings were saved in
        the locked state, it will lock (disable) all of the dialog's
        fields.
        """
        if locked:
            self.DisableFields()
            self.lockOrUnlockButton.SetLabel("Unlock")
        else:
            self.EnableFields()
            self.lockOrUnlockButton.SetLabel("Lock")

    def GetScheduleType(self):
        return self.scheduleTypeComboBox.GetValue()

    def SetScheduleType(self, scheduleType):
        self.scheduleTypeComboBox.SetValue(scheduleType)

    def IsMondayChecked(self):
        return self.mondayCheckBox.GetValue()

    def SetMondayChecked(self, checked):
        self.mondayCheckBox.SetValue(checked)

    def IsTuesdayChecked(self):
        return self.tuesdayCheckBox.GetValue()

    def SetTuesdayChecked(self, checked):
        self.tuesdayCheckBox.SetValue(checked)

    def IsWednesdayChecked(self):
        return self.wednesdayCheckBox.GetValue()

    def SetWednesdayChecked(self, checked):
        self.wednesdayCheckBox.SetValue(checked)

    def IsThursdayChecked(self):
        return self.thursdayCheckBox.GetValue()

    def SetThursdayChecked(self, checked):
        self.thursdayCheckBox.SetValue(checked)

    def IsFridayChecked(self):
        return self.fridayCheckBox.GetValue()

    def SetFridayChecked(self, checked):
        self.fridayCheckBox.SetValue(checked)

    def IsSaturdayChecked(self):
        return self.saturdayCheckBox.GetValue()

    def SetSaturdayChecked(self, checked):
        self.saturdayCheckBox.SetValue(checked)

    def IsSundayChecked(self):
        return self.sundayCheckBox.GetValue()

    def SetSundayChecked(self, checked):
        self.sundayCheckBox.SetValue(checked)

    def GetScheduledDate(self):
        wxDate = self.dateCtrl.GetValue()
        if wxDate.IsValid():
            ymd = map(int, wxDate.FormatISODate().split('-'))
            return datetime.date(datetime(*ymd))
        else:
            return None 

    def SetScheduledDate(self, date):
        timeTuple = date.timetuple()
        dmy = (timeTuple[2], timeTuple[1]-1, timeTuple[0])
        self.dateCtrl.SetValue(wx.DateTimeFromDMY(*dmy))

    def GetScheduledTime(self):
        wxDateTime = self.timeCtrl.GetValue(as_wxDateTime=True)
        timeString = wxDateTime.FormatTime()
        return datetime.time(datetime.strptime(timeString, "%H:%M:%S"))

    def SetScheduledTime(self, time):
        timeString = "%d:%d:%d" % (time.hour, time.minute, time.second)
        wxDateTime = wx.DateTime()
        wxDateTime.ParseTime(timeString)
        self.timeCtrl.SetValue(wxDateTime)

    def GetTimerMinutes(self):
        return self.timerNumCtrl.GetValue()

    def SetTimerMinutes(self, minutes):
        self.timerNumCtrl.SetValue(minutes)
        self.timerSpin.SetValue(minutes)

    def GetTimerFromTime(self):
        wxDateTime = self.fromTimeCtrl.GetValue(as_wxDateTime=True)
        timeString = wxDateTime.FormatTime()
        return datetime.time(datetime.strptime(timeString, "%H:%M:%S"))

    def SetTimerFromTime(self, time):
        timeString = "%d:%d:%d" % (time.hour, time.minute, time.second)
        wxDateTime = wx.DateTime()
        wxDateTime.ParseTime(timeString)
        self.fromTimeCtrl.SetValue(wxDateTime)

    def GetTimerToTime(self):
        wxDateTime = self.toTimeCtrl.GetValue(as_wxDateTime=True)
        timeString = wxDateTime.FormatTime()
        return datetime.time(datetime.strptime(timeString, "%H:%M:%S"))

    def SetTimerToTime(self, time):
        timeString = "%d:%d:%d" % (time.hour, time.minute, time.second)
        wxDateTime = wx.DateTime()
        wxDateTime.ParseTime(timeString)
        self.toTimeCtrl.SetValue(wxDateTime)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnOK(self, event):
        if self.GetInstrumentName() != \
                self.settingsModel.GetInstrumentName() and \
                self.settingsModel.GetInstrumentName() != "":
            instrumentNameMismatchEvent = mde.MyDataEvent(
                mde.EVT_INSTRUMENT_NAME_MISMATCH,
                settingsDialog=self,
                settingsModel=self.settingsModel,
                facilityName=self.GetFacilityName(),
                oldInstrumentName=self.settingsModel.GetInstrumentName(),
                newInstrumentName=self.GetInstrumentName())
            wx.PostEvent(wx.GetApp().GetMainFrame(),
                         instrumentNameMismatchEvent)
            return

        settingsDialogValidationEvent = \
            mde.MyDataEvent(mde.EVT_SETTINGS_DIALOG_VALIDATION,
                            settingsDialog=self,
                            settingsModel=self.settingsModel,
                            okEvent=event)

        intervalSinceLastConnectivityCheck = \
            datetime.now() - wx.GetApp().GetLastNetworkConnectivityCheckTime()
        # FIXME: Magic number of 30 seconds since last connectivity check.
        if intervalSinceLastConnectivityCheck.total_seconds() >= 30 or \
                not wx.GetApp().GetLastNetworkConnectivityCheckSuccess():
            checkConnectivityEvent = \
                mde.MyDataEvent(mde.EVT_CHECK_CONNECTIVITY,
                                settingsModel=self.settingsModel,
                                nextEvent=settingsDialogValidationEvent)
            wx.PostEvent(wx.GetApp().GetMainFrame(), checkConnectivityEvent)
        else:
            wx.PostEvent(wx.GetApp().GetMainFrame(),
                         settingsDialogValidationEvent)

    def OnBrowse(self, event):
        dlg = wx.DirDialog(self, "Choose a directory:",
                           defaultPath=self.GetDataDirectory()
                           .encode('ascii', 'ignore'))
        if dlg.ShowModal() == wx.ID_OK:
            self.dataDirectoryField.SetValue(dlg.GetPath())

    def UpdateFieldsFromModel(self, settingsModel):
        self.SetInstrumentName(settingsModel.GetInstrumentName())
        self.SetFacilityName(settingsModel.GetFacilityName())
        self.SetContactName(settingsModel.GetContactName())
        self.SetContactEmail(settingsModel.GetContactEmail())
        self.SetMyTardisUrl(settingsModel.GetMyTardisUrl())
        self.SetDataDirectory(settingsModel.GetDataDirectory())
        self.SetUsername(settingsModel.GetUsername())
        self.SetApiKey(settingsModel.GetApiKey())

        self.SetFolderStructure(settingsModel.GetFolderStructure())
        self.SetDatasetGrouping(settingsModel.GetDatasetGrouping())
        self.SetGroupPrefix(settingsModel.GetGroupPrefix())
        self.SetIgnoreOldDatasets(settingsModel.IgnoreOldDatasets())
        self.SetIgnoreOldDatasetIntervalNumber(
            settingsModel.GetIgnoreOldDatasetIntervalNumber())
        if settingsModel.IgnoreOldDatasets():
            self.ignoreDatasetsOlderThanSpinCtrl.Enable(True)
            self.intervalUnitsComboBox.Enable(True)
        ignoreIntervalUnit = settingsModel.GetIgnoreOldDatasetIntervalUnit()
        if ignoreIntervalUnit in self.intervalUnitsPlural and \
                self.showingSingularUnits:
            self.intervalUnitsComboBox.Clear()
            self.intervalUnitsComboBox.AppendItems(self.intervalUnitsPlural)
            self.showingSingularUnits = False
        elif ignoreIntervalUnit in self.intervalUnitsSingular and \
                not self.showingSingularUnits:
            self.intervalUnitsComboBox.Clear()
            self.intervalUnitsComboBox.AppendItems(self.intervalUnitsSingular)
            self.showingSingularUnits = True
        self.SetIgnoreOldDatasetIntervalUnit(
            settingsModel.GetIgnoreOldDatasetIntervalUnit())
        self.SetMaxUploadThreads(settingsModel.GetMaxUploadThreads())
        self.SetCheckForMissingFolders(settingsModel.CheckForMissingFolders())

        self.SetScheduleType(settingsModel.GetScheduleType())
        self.SetMondayChecked(settingsModel.IsMondayChecked())
        self.SetTuesdayChecked(settingsModel.IsTuesdayChecked())
        self.SetWednesdayChecked(settingsModel.IsWednesdayChecked())
        self.SetThursdayChecked(settingsModel.IsThursdayChecked())
        self.SetFridayChecked(settingsModel.IsFridayChecked())
        self.SetSaturdayChecked(settingsModel.IsSaturdayChecked())
        self.SetSundayChecked(settingsModel.IsSundayChecked())
        self.SetScheduledDate(settingsModel.GetScheduledDate())
        self.SetScheduledTime(settingsModel.GetScheduledTime())
        self.SetTimerMinutes(settingsModel.GetTimerMinutes())
        self.SetTimerFromTime(settingsModel.GetTimerFromTime())
        self.SetTimerToTime(settingsModel.GetTimerToTime())

        # This needs to go last, because it sets the enabled / disabled
        # state of many fields which depend on the values obtained from
        # the SettingsModel in the lines of code above.
        self.SetLocked(settingsModel.Locked())

    def OnPaste(self, event):
        textCtrl = wx.Window.FindFocus()
        if textCtrl is not None:
            if textCtrl == self.apiKeyField:
                textCtrl.Paste()
            else:
                event.Skip()

    def OnSelectAll(self, event):
        textCtrl = wx.Window.FindFocus()
        if textCtrl is not None:
            if textCtrl == self.apiKeyField:
                textCtrl.SelectAll()
            else:
                event.Skip()

    def OnSave(self, event):
        mydataConfigPath = self.settingsModel.GetConfigPath()
        if mydataConfigPath is not None:
            dlg = wx.FileDialog(wx.GetApp().GetMainFrame(),
                                "Save MyData configuration as...", "",
                                "%s.cfg" % self.GetInstrumentName(), "*.cfg",
                                wx.SAVE | wx.OVERWRITE_PROMPT)
            if dlg.ShowModal() == wx.ID_OK:
                configPath = dlg.GetPath()
                wx.GetApp().SetConfigPath(configPath)
                self.settingsModel.SetConfigPath(configPath)
                self.settingsModel\
                    .SaveFieldsFromDialog(self,
                                          configPath=configPath)
                if configPath != wx.GetApp().GetConfigPath():
                    self.settingsModel.SaveFieldsFromDialog(
                        self, configPath=wx.GetApp().GetConfigPath())

    def OnApiKeyFieldFocused(self, event):
        self.apiKeyField.SelectAll()

    def OnIgnoreOldDatasetsCheckBox(self, event):
        if event.IsChecked():
            self.ignoreDatasetsOlderThanSpinCtrl.SetValue(6)
            self.ignoreDatasetsOlderThanSpinCtrl.Enable(True)
            if self.showingSingularUnits:
                self.intervalUnitsComboBox.Clear()
                self.intervalUnitsComboBox\
                    .AppendItems(self.intervalUnitsPlural)
                self.showingSingularUnits = False
            self.intervalUnitsComboBox.SetValue("months")
            self.intervalUnitsComboBox.Enable(True)
        else:
            self.ignoreDatasetsOlderThanSpinCtrl.SetValue(1)
            self.ignoreDatasetsOlderThanSpinCtrl.Enable(False)
            if not self.showingSingularUnits:
                self.intervalUnitsComboBox.Clear()
                self.intervalUnitsComboBox\
                    .AppendItems(self.intervalUnitsSingular)
                self.showingSingularUnits = True
            self.intervalUnitsComboBox.SetValue("month")
            self.intervalUnitsComboBox.Enable(False)

    def OnIgnoreOldDatasetsSpinCtrl(self, event):
        if event.GetInt() == 1:
            if not self.showingSingularUnits:
                intervalUnitValue = self.intervalUnitsComboBox.GetValue()
                self.intervalUnitsComboBox.Clear()
                self.intervalUnitsComboBox\
                    .AppendItems(self.intervalUnitsSingular)
                self.intervalUnitsComboBox\
                    .SetValue(intervalUnitValue.replace('s', ''))
                self.showingSingularUnits = True
        else:
            if self.showingSingularUnits:
                intervalUnitValue = self.intervalUnitsComboBox.GetValue()
                self.intervalUnitsComboBox.Clear()
                self.intervalUnitsComboBox\
                    .AppendItems(self.intervalUnitsPlural)
                self.intervalUnitsComboBox.SetValue(intervalUnitValue + 's')
                self.showingSingularUnits = False

    def OnHelp(self, event):
        wx.BeginBusyCursor()
        import webbrowser
        webbrowser\
            .open("http://mydata.readthedocs.org/en/latest/settings.html")
        wx.EndBusyCursor()

    def OnSelectFolderStructure(self, event):
        folderStructure = self.folderStructureComboBox.GetValue()
        if folderStructure == 'Username / Dataset' or \
                folderStructure == 'Email / Dataset':
            self.datasetGroupingField\
                .SetValue("Instrument Name - Data Owner's Full Name")
            self.groupPrefixLabel.Show(False)
            self.groupPrefixField.Show(False)
        elif folderStructure == \
                'Username / "MyTardis" / Experiment / Dataset' or \
                folderStructure == 'Username / Experiment / Dataset' or \
                folderStructure == 'Email / Experiment / Dataset':
            self.datasetGroupingField.SetValue("Experiment")
            self.groupPrefixLabel.Show(False)
            self.groupPrefixField.Show(False)
        elif folderStructure == \
                'User Group / Instrument / Full Name / Dataset':
            self.datasetGroupingField.SetValue("Instrument - Full Name")
            self.groupPrefixLabel.Show(True)
            self.groupPrefixField.Show(True)

    def OnDropFiles(self, filepaths):
        if self.Locked():
            message = \
                "Please unlock MyData's settings before importing " \
                "a configuration file."
            dlg = wx.MessageDialog(None, message, "MyData - Settings Locked",
                                   wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            return
        self.settingsModel.SetConfigPath(filepaths[0])
        self.settingsModel.LoadSettings()
        self.UpdateFieldsFromModel(self.settingsModel)

        folderStructure = self.folderStructureComboBox.GetValue()
        if folderStructure == \
                'User Group / Instrument / Full Name / Dataset':
            self.groupPrefixLabel.Show(True)
            self.groupPrefixField.Show(True)
        else:
            self.groupPrefixLabel.Show(False)
            self.groupPrefixField.Show(False)

    def OnLockOrUnlockSettings(self, event):
        if self.lockOrUnlockButton.GetLabel() == "Lock":
            message = "Once settings have been locked, only an administrator " \
                "will be able to unlock them.\n\n" \
                "Are you sure you want to lock MyData's settings?"
            confirmationDialog = \
                wx.MessageDialog(None, message, "MyData - Lock Settings",
                                 wx.YES | wx.NO | wx.ICON_QUESTION)
            okToLock = confirmationDialog.ShowModal()
            if okToLock != wx.ID_YES:
                return
            lockingSettings = True
            unlockingSettings = False
            logger.debug("Locking settings.")
            self.lockOrUnlockButton.SetLabel("Unlock")
        else:
            lockingSettings = False
            unlockingSettings = True
            logger.debug("Requesting privilege elevation and "
                         "unlocking settings.")
            if sys.platform.startswith("win"):
                import win32com.shell.shell as shell
                import win32con
                from win32com.shell import shellcon
                import ctypes
                runningAsAdmin = ctypes.windll.shell32.IsUserAnAdmin()
                params = "--version "

                if not runningAsAdmin:
                    logger.info("Attempting to run \"%s --version\" "
                                "as an administrator." % sys.executable)
                    try:
                        procInfo = shell.ShellExecuteEx(
                            nShow=win32con.SW_SHOWNORMAL,
                            fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
                            lpVerb='runas',
                            lpFile=sys.executable,
                            lpParameters=params)
                        procHandle = procInfo['hProcess']
                    except:
                        logger.error("User privilege elevation failed.")
                        logger.debug(traceback.format_exc())
                        return
            elif sys.platform.startswith("darwin"):
                logger.info("Attempting to run "
                            "\"echo MyData privilege elevation\" "
                            "as an administrator.")
                returncode = os.system("osascript -e "
                                       "'do shell script "
                                       "\"echo MyData privilege elevation\" "
                                       "with administrator privileges'")
                if returncode != 0:
                    raise Exception("Failed to get admin privileges.")
            self.lockOrUnlockButton.SetLabel("Lock")

        self.EnableFields(unlockingSettings)

    def EnableFields(self, enabled=True):
        # General tab
        self.instrumentNameField.Enable(enabled)
        self.facilityNameField.Enable(enabled)
        self.contactNameField.Enable(enabled)
        self.contactEmailField.Enable(enabled)
        self.dataDirectoryField.Enable(enabled)
        self.browseDataDirectoryButton.Enable(enabled)
        self.myTardisUrlField.Enable(enabled)
        self.usernameField.Enable(enabled)
        self.apiKeyField.Enable(enabled)

        # Schedule tab
        self.scheduleTypeComboBox.Enable(enabled)
        # Disable everything, then determine
        # what needs to be re-enabled by calling
        # self.OnScheduleTypeChange()
        self.mondayCheckBox.Enable(False)
        self.tuesdayCheckBox.Enable(False)
        self.wednesdayCheckBox.Enable(False)
        self.thursdayCheckBox.Enable(False)
        self.fridayCheckBox.Enable(False)
        self.saturdayCheckBox.Enable(False)
        self.sundayCheckBox.Enable(False)
        self.dateCtrl.Enable(False)
        self.timeCtrl.Enable(False)
        self.timerNumCtrl.Enable(False)
        self.fromTimeCtrl.Enable(False)
        self.toTimeCtrl.Enable(False)
        if enabled:
            self.OnScheduleTypeChange(None)

        # Advanced tab
        self.folderStructureComboBox.Enable(enabled)
        self.datasetGroupingField.Enable(enabled)
        self.groupPrefixField.Enable(enabled)
        self.checkForMissingFoldersCheckBox.Enable(enabled)
        self.ignoreDatasetsOlderThanCheckBox.Enable(enabled)
        self.ignoreDatasetsOlderThanSpinCtrl\
            .Enable(enabled)
        self.intervalUnitsComboBox.Enable(enabled)
        self.maximumUploadThreadsSpinCtrl.Enable(enabled)
        self.Update()

    def DisableFields(self):
        self.EnableFields(False)

    def OnSpinTimer(self, event):
        self.timerNumCtrl.SetValue(event.GetPosition())

    def OnScheduleTypeChange(self, event):
        scheduleType = self.scheduleTypeComboBox.GetValue()
        enableDaysOfWeekCheckBoxes = (scheduleType == "Weekly")
        self.mondayCheckBox.Enable(enableDaysOfWeekCheckBoxes)
        self.tuesdayCheckBox.Enable(enableDaysOfWeekCheckBoxes)
        self.wednesdayCheckBox.Enable(enableDaysOfWeekCheckBoxes)
        self.thursdayCheckBox.Enable(enableDaysOfWeekCheckBoxes)
        self.fridayCheckBox.Enable(enableDaysOfWeekCheckBoxes)
        self.saturdayCheckBox.Enable(enableDaysOfWeekCheckBoxes)
        self.sundayCheckBox.Enable(enableDaysOfWeekCheckBoxes)
        enableDate = (scheduleType == "Once")
        self.dateCtrl.Enable(enableDate)
        enableTime = (scheduleType == "Once" or scheduleType == "Daily" or
                      scheduleType == "Weekly")
        self.timeCtrl.Enable(enableTime)
        enableTimer = (scheduleType == "Timer")
        self.timerNumCtrl.Enable(enableTimer)
        self.fromTimeCtrl.Enable(enableTimer)
        self.toTimeCtrl.Enable(enableTimer)
