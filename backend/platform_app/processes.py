"""Own trusted media helper trees without relying on Windows process enumeration."""
import os,subprocess,ctypes
from pathlib import Path

def attach_job(child):
    if os.name!='nt':return
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',wintypes.DWORD),('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',wintypes.DWORD),('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
    class IO(ctypes.Structure):_fields_=[('values',ctypes.c_ulonglong*6)]
    class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('process_mem',ctypes.c_size_t),('job_mem',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    handle=kernel.CreateJobObjectW(None,None);info=Extended();info.basic.flags=0x2000 # KILL_ON_JOB_CLOSE
    if not handle or not kernel.SetInformationJobObject(handle,9,ctypes.byref(info),ctypes.sizeof(info)) or not kernel.AssignProcessToJobObject(handle,int(child._handle)):
        if handle:ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(handle))
        child.kill();child.wait(timeout=5);raise OSError('Cannot establish media process containment')
    child._mathmodel_job=handle

def spawn_helper(command,env):
    gate=Path(env['TEMP'])/'helper-start'
    child=subprocess.Popen(command+['--start-gate',str(gate)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,start_new_session=os.name!='nt')
    try:attach_job(child);gate.touch()
    except BaseException:
        if child.poll() is None:child.kill();child.wait(timeout=5)
        close_job(child);raise
    return child

def terminate_tree(child):
    if os.name=='nt':
        handle=getattr(child,'_mathmodel_job',None)
        if not handle:raise RuntimeError('Media helper has no owned Job Object')
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        if not kernel.TerminateJobObject(ctypes.c_void_p(handle),1):raise OSError('Cannot terminate media job')
    else:
        import signal
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass

def close_job(child):
    handle=getattr(child,'_mathmodel_job',None)
    if handle:ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(handle));child._mathmodel_job=None
