import win32serviceutil
import win32service
import traceback
import pywintypes

# See here for possible service statuses:
# https://msdn.microsoft.com/en-us/library/aa394418%28v=vs.85%29.aspx
# e.g. 
# win32service.SERVICE_START_PENDING
# win32service.SERVICE_STOP_PENDING
# win32service.SERVICE_CONTINUE_PENDING
# win32service.SERVICE_DEMAND_START
# ...

try:
    serviceStatus = win32serviceutil.QueryServiceStatus("App Readiness")
    if serviceStatus[1] == win32service.SERVICE_RUNNING:
        print "App Readiness service is running."
    elif serviceStatus[1] == win32service.SERVICE_STOPPED:
        print "App Readiness service is stopped."
    else:
        print "App Readiness service's status is something else."
except pywintypes.error, e:
    print "pywintypes.error: " + str(e)
except:
    print traceback.format_exc()

try:
    serviceStatus = win32serviceutil.QueryServiceStatus("Apple Mobile Device")
    if serviceStatus[1] == win32service.SERVICE_RUNNING:
        print "Apple Mobile Device service is running."
    elif serviceStatus[1] == win32service.SERVICE_STOPPED:
        print "Apple Mobile Device service is stopped."
    else:
        print "Apple Mobile Device service's status is something else."
except pywintypes.error, e:
    print "pywintypes.error: " + str(e)
except:
    print traceback.format_exc()

try:
    serviceStatus = win32serviceutil.QueryServiceStatus("MyData")
    if serviceStatus[1] == win32service.SERVICE_RUNNING:
        print "MyData service is running."
    elif serviceStatus[1] == win32service.SERVICE_STOPPED:
        print "MyData service is stopped."
    else:
        print "MyData service's status is something else."
except pywintypes.error, e:
    if "does not exist as an installed service" in str(e):
        print "The MyData service is not installed."
    # print "pywintypes.error: " + str(e)
    # print "pywintypes.error code: " + str(int(e))
except:
    print traceback.format_exc()

