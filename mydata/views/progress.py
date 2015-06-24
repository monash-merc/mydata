# MyData - easy data uploads to the MyTardis research data management system
# Copyright (c) 2012-2013, Monash e-Research Centre (Monash University,
# Australia) All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# In addition, redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
# -  Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# -  Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# -  Neither the name of the Monash University nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE. SEE THE GNU GENERAL PUBLIC LICENSE FOR MORE
# DETAILS.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Enquiries: store.star.help@monash.edu

import wx
from mydata.logs import logger


class MyDataProgressDialog(wx.Frame):
    def __init__(self, parent, id, title, initialUserFoldersMessage, maxValue,
                 userCanAbort, cancelCallback=None):
        wx.Frame.__init__(self, parent, id, title,
                          style=wx.DEFAULT_DIALOG_STYLE
                          | wx.FRAME_FLOAT_ON_PARENT)
        self.userRequestedAbort = False
        self.cancelCallback = cancelCallback
        self.panel = wx.Panel(self, wx.ID_ANY)
        self.userFoldersMessageLabel = \
            wx.StaticText(self.panel,label=initialUserFoldersMessage)
        self.userFoldersGauge = wx.Gauge(self, -1, maxValue)

        statusMessageWidth = self.userFoldersMessageLabel.GetSize().width
        statusMessageWidth = max(statusMessageWidth, 300)
        self.userFoldersMessageLabel.SetMinSize(wx.Size(statusMessageWidth, -1))
        self.userFoldersGauge.SetSize(wx.Size(statusMessageWidth, -1))

        if userCanAbort:
            sizer = wx.FlexGridSizer(rows=7, cols=3, vgap=5, hgap=15)
        else:
            sizer = wx.FlexGridSizer(rows=6, cols=3, vgap=5, hgap=15)

        sizer.AddGrowableCol(1)

        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))
        sizer.Add(self.userFoldersMessageLabel,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
                  border=15)
        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))

        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))
        sizer.Add(self.userFoldersGauge,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))

        self.verificationsMessageLabel = wx.StaticText(self.panel, label="")
        self.verificationsGauge = wx.Gauge(self, -1, maxValue)
        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))
        sizer.Add(self.verificationsMessageLabel,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
                  border=15)
        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))

        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))
        sizer.Add(self.verificationsGauge,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))

        self.uploadsMessageLabel = wx.StaticText(self.panel, label="")
        self.uploadsGauge = wx.Gauge(self, -1, maxValue)
        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))
        sizer.Add(self.uploadsMessageLabel,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
                  border=15)
        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))

        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))
        sizer.Add(self.uploadsGauge,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))

        if userCanAbort:
            self.Bind(wx.EVT_CLOSE, self.OnCancel)
            sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))
            CANCEL_BUTTON_ID = wx.NewId()
            self.cancelButton = wx.Button(self.panel, CANCEL_BUTTON_ID,
                                          "Cancel")
            self.Bind(wx.EVT_BUTTON, self.OnCancel, id=CANCEL_BUTTON_ID)
            sizer.Add(self.cancelButton,
                      flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=15)
            sizer.Add(wx.StaticText(self.panel, wx.ID_ANY, " "))
        else:
            self.Bind(wx.EVT_CLOSE, self.DoNothing)

        self.panel.SetSizerAndFit(sizer)
        self.Fit()
        self.userFoldersMessageLabel.SetLabel(initialUserFoldersMessage)
        self.Center()
        self.Show()

        return None

    def ShouldAbort(self):
        return self.userRequestedAbort

    def DoNothing(self, event):
        logger.debug("User tried to close the progress dialog, "
                     "even though userCanAbort is False.")

    def OnCancel(self, event):
        self.userFoldersMessageLabel.SetLabel("Aborting...")
        self.userRequestedAbort = True
        self.cancelButton.Enable(False)
        if self.cancelCallback is not None:
            self.cancelCallback()

    def SetCancelCallback(self, callback):
        self.cancelCallback = callback

    def UpdateUserFoldersGauge(self, value, message):
        if self.userRequestedAbort:
            return
        self.userFoldersGauge.SetValue(value)
        self.userFoldersMessageLabel.SetLabel(message)

    def UpdateVerificationsGauge(self, value, message):
        if self.userRequestedAbort:
            return
        self.verificationsGauge.SetValue(value)
        self.verificationsMessageLabel.SetLabel(message)

    def UpdateUploadsGauge(self, value, message):
        if self.userRequestedAbort:
            return
        self.uploadsGauge.SetValue(value)
        self.uploadsMessageLabel.SetLabel(message)

    def SetUserFoldersRange(self, maxValue):
        self.userFoldersGauge.SetRange(maxValue)

    def SetVerificationsRange(self, maxValue):
        self.verificationsGauge.SetRange(maxValue)

    def SetUploadsRange(self, maxValue):
        self.uploadsGauge.SetRange(maxValue)
