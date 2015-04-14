def PidIsRunning(pid):
    try:
        import psutil
        p = psutil.Process(int(pid))
        if p.status == psutil.STATUS_DEAD:
            return False
        if p.status == psutil.STATUS_ZOMBIE:
            return False
        return True # Assume other status are valid
    except psutil.NoSuchProcess:
        return False
    except ImportError:
        logger.error('Python installation missing the psutil module')
        return True
