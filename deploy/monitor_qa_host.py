"""Bounded, read-only measurements for the isolated shared-server QA workload."""
import argparse, json, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

PROJECT='mathmodel-qa-20261024'
GROUP=Path('/sys/fs/cgroup/mathmodel.slice/mathmodel-qa.slice')
def command(args):
    r=subprocess.run(args,capture_output=True,text=True,timeout=12)
    return r.returncode,r.stdout.strip()
def sample():
    mem={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
    services={s:command(['systemctl','is-active',s])[1] for s in ['nginx','pm2-root','elfred-typesense','bt']}
    row={'utc':datetime.now(timezone.utc).isoformat(),'load':Path('/proc/loadavg').read_text().split()[:3],
         'availableMiB':round(mem['MemAvailable']/1024,1),'swapUsedMiB':round((mem['SwapTotal']-mem['SwapFree'])/1024,1),'oldServices':services}
    for name in ['memory.current','memory.peak','memory.events','memory.swap.current','cpu.stat']:
        if (GROUP/name).exists():row['qa_'+name]=(GROUP/name).read_text().strip()
    rc,ids=command(['docker','ps','-aq','--filter','label=com.docker.compose.project='+PROJECT])
    containers=[]
    if rc==0 and ids:
        # Docker inspect's full output contains env/secrets metadata. Select only state/resource fields.
        template='{{json .Name}} {{json .State.OOMKilled}} {{json .State.Status}} {{json .RestartCount}} {{json .HostConfig.Memory}} {{json .HostConfig.MemorySwap}} {{json .HostConfig.CgroupParent}}'
        for ident in ids.splitlines():
            _,details=command(['docker','inspect','--format',template,ident])
            item={'limitsAndState':details}
            _,pid=command(['docker','inspect','--format','{{.State.Pid}}',ident])
            if pid.isdigit() and int(pid)>0:
                path=Path('/sys/fs/cgroup')/Path('/proc/'+pid+'/cgroup').read_text().strip().split('::')[1].lstrip('/')
                item['actualCgroup']=str(path)
                item['inQaSlice']=path.is_relative_to(GROUP)
                for field in ['memory.current','memory.peak','memory.events','memory.swap.current']:
                    item[field]=(path/field).read_text().strip()
            containers.append(item)
    row['qaContainers']=containers
    return row
def main():
    p=argparse.ArgumentParser();p.add_argument('--duration',type=int,default=0);p.add_argument('--interval',type=int,default=5);a=p.parse_args()
    assert 0<=a.duration<=3600 and 2<=a.interval<=60
    deadline=time.monotonic()+a.duration
    while True:
        print(json.dumps(sample(),ensure_ascii=False),flush=True)
        if time.monotonic()>=deadline:break
        time.sleep(a.interval)
if __name__=='__main__':main()
