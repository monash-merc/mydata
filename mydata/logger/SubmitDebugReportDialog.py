import wx
import os
import sys
import traceback
import ConfigParser

if os.path.abspath("..") not in sys.path:
    sys.path.append(os.path.abspath(".."))


class SubmitDebugReportDialog(wx.Dialog):
    def __init__(self, parent, id, title, debugLog, settingsModel):
        wx.Dialog.__init__(self, parent, id, title, wx.DefaultPosition)

        self.settingsModel = settingsModel

        self.submitDebugReportDialogSizer = wx.FlexGridSizer(rows=1, cols=1)
        self.SetSizer(self.submitDebugReportDialogSizer)

        self.submitDebugReportDialogPanel = wx.Panel(self, wx.ID_ANY)
        self.submitDebugReportDialogPanelSizer = wx.FlexGridSizer(10, 1)
        self.submitDebugReportDialogPanel\
            .SetSizer(self.submitDebugReportDialogPanelSizer)

        self.submitDebugReportDialogSizer\
            .Add(self.submitDebugReportDialogPanel,
                 flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=15)

        # Instructions label

        instructionsText = \
            "You can submit a debug report to the MyData developers."
        self.instructionsLabel = \
            wx.StaticText(self.submitDebugReportDialogPanel, wx.ID_ANY,
                          instructionsText)
        self.instructionsLabel.SetMinSize(wx.Size(600, wx.ID_ANY))
        self.submitDebugReportDialogPanelSizer\
            .Add(self.instructionsLabel, flag=wx.EXPAND | wx.BOTTOM, border=15)

        # Contact details panel

        self.contactDetailsPanel = wx.Panel(self.submitDebugReportDialogPanel,
                                            wx.ID_ANY)

        self.contactDetailsGroupBox = \
            wx.StaticBox(self.contactDetailsPanel, wx.ID_ANY,
                         label="Contact details")
        self.contactDetailsGroupBoxSizer = \
            wx.StaticBoxSizer(self.contactDetailsGroupBox, wx.VERTICAL)
        self.contactDetailsPanel.SetSizer(self.contactDetailsGroupBoxSizer)

        self.innerContactDetailsPanel = wx.Panel(self.contactDetailsPanel,
                                                 wx.ID_ANY)
        self.innerContactDetailsPanelSizer = wx.FlexGridSizer(5, 2, hgap=10)
        self.innerContactDetailsPanel\
            .SetSizer(self.innerContactDetailsPanelSizer)

        self.innerContactDetailsPanelSizer.AddGrowableCol(1)

        # Name

        self.nameLabel = wx.StaticText(self.innerContactDetailsPanel,
                                       wx.ID_ANY, "Name:")
        self.innerContactDetailsPanelSizer.Add(self.nameLabel)

        contact_name = self.settingsModel.GetContactName()

        self.nameField = wx.TextCtrl(self.innerContactDetailsPanel, wx.ID_ANY)
        self.nameField.SetValue(contact_name)
        self.innerContactDetailsPanelSizer.Add(self.nameField, flag=wx.EXPAND)

        # Blank space

        self.innerContactDetailsPanelSizer\
            .Add(wx.StaticText(self.innerContactDetailsPanel, wx.ID_ANY, ""))
        self.innerContactDetailsPanelSizer\
            .Add(wx.StaticText(self.innerContactDetailsPanel, wx.ID_ANY, ""))

        # Email

        self.emailLabel = wx.StaticText(self.innerContactDetailsPanel,
                                        wx.ID_ANY, "Email address:")
        self.innerContactDetailsPanelSizer.Add(self.emailLabel)

        contact_email = self.settingsModel.GetContactEmail()

        self.emailField = wx.TextCtrl(self.innerContactDetailsPanel, wx.ID_ANY)
        self.emailField.SetValue(contact_email)
        self.innerContactDetailsPanelSizer.Add(self.emailField, flag=wx.EXPAND)

        # Blank space

        self.innerContactDetailsPanelSizer\
            .Add(wx.StaticText(self.innerContactDetailsPanel, wx.ID_ANY, ""))
        self.innerContactDetailsPanelSizer\
            .Add(wx.StaticText(self.innerContactDetailsPanel, wx.ID_ANY, ""))

        # Please contact me

        self.blankLabel = wx.StaticText(self.innerContactDetailsPanel,
                                        wx.ID_ANY, "")
        self.innerContactDetailsPanelSizer.Add(self.blankLabel)

        self.pleaseContactMeCheckBox = \
            wx.CheckBox(self.innerContactDetailsPanel, wx.ID_ANY,
                        "Please contact me")

        self.innerContactDetailsPanelSizer.Add(self.pleaseContactMeCheckBox,
                                               flag=wx.EXPAND)

        self.innerContactDetailsPanel.Fit()
        self.contactDetailsGroupBoxSizer.Add(self.innerContactDetailsPanel,
                                             flag=wx.EXPAND)
        self.contactDetailsPanel.Fit()

        self.submitDebugReportDialogPanelSizer.Add(self.contactDetailsPanel,
                                                   flag=wx.EXPAND)

        # Blank space

        self.submitDebugReportDialogPanelSizer\
            .Add(wx.StaticText(self.submitDebugReportDialogPanel,
                               wx.ID_ANY, ""))

        # Comments panel

        self.commentsPanel = wx.Panel(self.submitDebugReportDialogPanel,
                                      wx.ID_ANY)

        self.commentsGroupBox = wx.StaticBox(self.commentsPanel, wx.ID_ANY,
                                             label="Comments")
        self.commentsGroupBoxSizer = wx.StaticBoxSizer(self.commentsGroupBox,
                                                       wx.VERTICAL)
        self.commentsPanel.SetSizer(self.commentsGroupBoxSizer)

        self.innerCommentsPanel = wx.Panel(self.commentsPanel, wx.ID_ANY)
        self.innerCommentsPanelSizer = wx.FlexGridSizer(10, 2, hgap=10)
        self.innerCommentsPanelSizer.AddGrowableCol(0)
        self.innerCommentsPanel.SetSizer(self.innerCommentsPanelSizer)

        self.commentsField = wx.TextCtrl(self.innerCommentsPanel, wx.ID_ANY,
                                         style=wx.TE_MULTILINE)
        self.commentsField.SetMinSize(wx.Size(wx.ID_ANY, 100))
        self.innerCommentsPanelSizer.Add(self.commentsField, flag=wx.EXPAND)

        if self.nameField.GetValue().strip() == "":
            self.nameField.SetFocus()
        elif self.emailField.GetValue().strip() == "":
            self.emailField.SetFocus()
        else:
            self.commentsField.SetFocus()

        self.innerCommentsPanel.Fit()
        self.commentsGroupBoxSizer.Add(self.innerCommentsPanel, flag=wx.EXPAND)
        self.commentsPanel.Fit()

        self.submitDebugReportDialogPanelSizer.Add(self.commentsPanel,
                                                   flag=wx.EXPAND)

        # Blank space

        self.submitDebugReportDialogPanelSizer\
            .Add(wx.StaticText(self.submitDebugReportDialogPanel,
                               wx.ID_ANY, ""))

        # Debug log panel

        self.debugLogPanel = wx.Panel(self.submitDebugReportDialogPanel,
                                      wx.ID_ANY)

        self.debugLogGroupBox = wx.StaticBox(self.debugLogPanel, wx.ID_ANY,
                                             label="Debug log")
        self.debugLogGroupBoxSizer = wx.StaticBoxSizer(self.debugLogGroupBox,
                                                       wx.VERTICAL)
        self.debugLogPanel.SetSizer(self.debugLogGroupBoxSizer)

        self.innerDebugLogPanel = wx.Panel(self.debugLogPanel, wx.ID_ANY)
        self.innerDebugLogPanelSizer = wx.FlexGridSizer(10, 2, hgap=10)
        self.innerDebugLogPanelSizer.AddGrowableCol(0)
        self.innerDebugLogPanel.SetSizer(self.innerDebugLogPanelSizer)

        smallFont = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        if sys.platform.startswith("darwin"):
            smallFont.SetPointSize(11)

        self.debugLogField = \
            wx.TextCtrl(self.innerDebugLogPanel, wx.ID_ANY,
                        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.debugLogField.SetValue(debugLog)
        self.debugLogField.SetFont(smallFont)
        self.debugLogField.SetMinSize(wx.Size(wx.ID_ANY, 100))
        self.innerDebugLogPanelSizer.Add(self.debugLogField, flag=wx.EXPAND)

        self.innerDebugLogPanel.Fit()
        self.debugLogGroupBoxSizer.Add(self.innerDebugLogPanel, flag=wx.EXPAND)
        self.debugLogPanel.Fit()

        self.submitDebugReportDialogPanelSizer.Add(self.debugLogPanel,
                                                   flag=wx.EXPAND)

        # Blank space

        self.submitDebugReportDialogPanelSizer\
            .Add(wx.StaticText(self.submitDebugReportDialogPanel,
                               wx.ID_ANY, ""))
        self.submitDebugReportDialogPanelSizer\
            .Add(wx.StaticText(self.submitDebugReportDialogPanel,
                               wx.ID_ANY, ""))

        # Buttons panel

        self.buttonsPanel = wx.Panel(self.submitDebugReportDialogPanel,
                                     wx.ID_ANY)
        self.buttonsPanelSizer = wx.FlexGridSizer(1, 5, hgap=10, vgap=5)
        self.buttonsPanel.SetSizer(self.buttonsPanelSizer)

        self.cancelButton = wx.Button(self.buttonsPanel, wx.NewId(), "Cancel")
        self.buttonsPanelSizer.Add(self.cancelButton, flag=wx.BOTTOM, border=5)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=self.cancelButton.GetId())

        self.submitButton = wx.Button(self.buttonsPanel, wx.NewId(), "Submit")
        self.submitButton.SetDefault()
        self.Bind(wx.EVT_BUTTON, self.OnSubmit, id=self.submitButton.GetId())
        self.buttonsPanelSizer.Add(self.submitButton, flag=wx.BOTTOM, border=5)

        self.buttonsPanel.Fit()

        self.submitDebugReportDialogPanelSizer.Add(self.buttonsPanel,
                                                   flag=wx.ALIGN_RIGHT)

        # Calculate positions on dialog, using sizers

        self.submitDebugReportDialogPanel.Fit()
        self.Fit()

        self.CenterOnParent()

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnSubmit(self, event):
        self.EndModal(wx.ID_OK)

    def GetName(self):
        return self.nameField.GetValue().strip()

    def GetEmail(self):
        return self.emailField.GetValue().strip()

    def GetComments(self):
        return self.commentsField.GetValue().strip()

    def GetPleaseContactMe(self):
        return self.pleaseContactMeCheckBox.GetValue()
