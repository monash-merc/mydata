MyData Client and Daemon
========================

Here's what the MyData daemon looks like when we first run it:

::

    $ python MyData.py --daemon
    MyData Daemon 0.2.1 (PID 4428)
    Connected to MemCache Daemon (PID 5056).
    Waiting for MyData client(s) to connect...

And here's what the MyData client looks like when we first run it:

::

    $ python MyData.py --client
    MyData Client 0.2.1 (PID 5836)
    Connected to MemCache Daemon (PID 5056).
    Connected to MyData Daemon (PID 4428).

    TO DO: Client should be able to retrieve already-running state from daemon
    (e.g. 'displaying 10 uploads in progress'), rather than just retrieving
    incremental updates ('AddRow') from the daemon.

Plus the client would be displaying the standard MyData GUI at that point.
After pressing OK on the MyData client's settings dialog, instead of running
the folder scans and uploads in the client process, the client sends a job
request to the daemon to perform the folder scans and uploads.  The job request
can be see in the daemon's log (~/.MyData_daemon_debug_log.txt) below:

::

    2015-04-14 22:22:05,207 - Daemon.py - 117 - run - MyData - DEBUG - job_1: {'requested': datetime.datetime(2015, 4, 14, 22, 22, 5, 161000), 'settingsModel': <SettingsModel.SettingsModel object at 0x043FC8D0>, 'methodName': 'OnRefresh'}

With a shared memory system like Memcached, there is a risk of concurrency
errors if you are not careful.  However, the "incr()" and "decr()" methods
provided are thread-safe, so we use "incr()" to increment the job ID, and then
create a key/value pair in Memcached with "job_<ID>" i.e. "job_1" as the key.
The maximum job ID requested by the MyData client can be stored in Memcached
and safely incrementd using "incr()".  And similarly, the maximum job ID which
has already been handled by the daemon can too be safely incremented using
"incr()" method in Memcached.

Once the MyData daemon begins running the job, it starts to report events back
to Memcached, which can be handled by the client:

::

    2015-04-14 22:22:05,598 - Daemon.py - 139 - run - MyData - DEBUG - event_1: {'eventType': 'SetStatusMessage', 'message': 'Validating settings...'}

In the case above, the daemon is reporting to the client that it is currently
validating the settings provided, (which may have already been validated by
the client), and that the status bar message needs to be updated to reflect
this.

If we now look in the MyData client log (~/.MyData_client_debug_log.txt), we
can see this "SetStatusMessage" event being handled by the MyData client:

::

   2015-04-14 22:22:05,566 - Client.py - 164 - run - MyData - DEBUG - Handled event of type: SetStatusMessage 

If all goes well, events will continue to propagate from the daemon to the
client and the user will be able to observe the progress almost as quickly as
if the client were running the tasks itself.
