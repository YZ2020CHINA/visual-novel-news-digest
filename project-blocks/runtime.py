"""Initialize one independent project canvas and launch its loopback service."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

SKILL = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / 'assets/template'
COLORS = dict(prologue='#9b8aff', route='#72a8f8', common='#73d2b3', character='#e6b66d', branch='#f295ac', ending='#b0cb70')

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

@contextmanager
def project_lock(root):
    lock, deadline = root / '.initialize.lock', time.monotonic() + 12
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError('工程正在初始化，稍后重试；异常退出时请检查 .initialize.lock')
            time.sleep(.1)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)

def validate(project, server):
    spec = importlib.util.spec_from_file_location('project_blocks_check', server)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate(project)

def build_project(title, plan=None):
    plan = plan or {'nodes': [
        {'id':'requirements','title':'确认需求与范围','type':'prologue','summary':'根据实际目标填写范围。','acceptance':['明确主要场景与交付范围']},
        {'id':'implementation','title':'实现项目功能','type':'common','summary':'根据项目拆分具体模块与工序。','acceptance':['实现已确认的需求','记录相关文件和检查结果']},
        {'id':'verification','title':'验证与交付','type':'ending','summary':'按实际检查结果验收。','acceptance':['检查主要使用流程','记录验证证据与尚存问题']}
    ], 'edges':[{'from':'requirements','to':'implementation'},{'from':'implementation','to':'verification'}]}
    if not isinstance(plan, dict) or not isinstance(plan.get('nodes'), list) or not plan['nodes']:
        raise ValueError('计划需要非空 nodes 数组')
    nodes = []
    for i, item in enumerate(plan['nodes']):
        node_id, kind = item.get('id', f'task_{i+1}'), item.get('type','common')
        if not isinstance(node_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',node_id) or kind not in COLORS:
            raise ValueError('计划节点 ID 或积木类型无效')
        nodes.append(dict(id=node_id,title=item.get('title',node_id),routeType=kind,color=COLORS[kind],
            x=60+(i%4)*440,y=80+(i//4)*370,characters=item.get('owner','Codex'),location=', '.join(item.get('files',[])),bgm=item.get('deliverable',''),
            summary=item.get('summary',''),script=item.get('instructions',''),image='',choices=[],
            workflow=dict(status='todo',priority=item.get('priority','P1'),files=item.get('files',[]),acceptance=item.get('acceptance',[]),blockReason='',evidence=[])))
    by_id = {n['id']:n for n in nodes}
    if len(by_id)!=len(nodes):
        raise ValueError('计划节点 ID 重复')
    for i,edge in enumerate(plan.get('edges',[])):
        if edge.get('from') not in by_id or edge.get('to') not in by_id:
            raise ValueError('关系目标不存在')
        rel=edge.get('type','前置依赖')
        by_id[edge['from']]['choices'].append(dict(id=f'rel_{i+1}',text=rel,tag=rel,target=edge['to']))
    return dict(title=title,version='1.0',viewport=dict(x=35,y=55,scale=.75),nodes=nodes,groups=[],stickyNotes=[],customRoutes=[])

def matches(url,data):
    if not isinstance(url,str) or not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}',url):
        return False
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url.rstrip('/')+'/api/info',timeout=.5) as response:
            info=json.load(response)
        return info.get('app')=='project-blocks' and Path(info.get('dataFile','')).resolve()==data.resolve()
    except (OSError,ValueError):
        return False

def start(root,port=None):
    data,state=root/'data/project.json',root/'.runtime.json'
    if state.exists():
        try:
            old=json.loads(state.read_text(encoding='utf-8'))
            if matches(old['url'],data):
                return dict(url=old['url'],reused=True)
        except (OSError,ValueError,KeyError):
            pass
    stable=8800+int(hashlib.sha256(str(data.resolve()).encode()).hexdigest()[:6],16)%1000
    for candidate in ([port] if port else range(stable,stable+30)):
        url=f'http://127.0.0.1:{candidate}'
        if matches(url,data):
            atomic_json(state,dict(url=url,dataFile=str(data),port=candidate))
            return dict(url=url,reused=True)
        command=[sys.executable,str(root/'server.py'),'--no-browser','--port',str(candidate),'--data',str(data)]
        kwargs=dict(cwd=str(root),stdin=subprocess.DEVNULL,env={**os.environ,'PYTHONUTF8':'1'})
        if os.name=='nt':
            kwargs['creationflags']=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session']=True
        with (root/'server.log').open('ab') as log:
            process=subprocess.Popen(command,stdout=log,stderr=log,**kwargs)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and process.poll() is None:
            if matches(url,data):
                atomic_json(state,dict(url=url,dataFile=str(data),port=candidate,pid=process.pid))
                return dict(url=url,reused=False)
            time.sleep(.12)
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
    raise RuntimeError('无法启动工程画布；请查看 project-blocks/server.log')

def ensure(project_root,title=None,plan_path=None,launch=False,port=None,template=None):
    project_root=Path(project_root).resolve(strict=True)
    if not project_root.is_dir() or project_root==Path(project_root.anchor) or project_root==Path.home():
        raise ValueError('请指定实际项目目录，不能使用主目录或磁盘根目录')
    root=project_root/'project-blocks'
    if root.is_symlink():
        raise ValueError('目标不能是符号链接')
    root.mkdir(exist_ok=True)
    if not root.resolve().is_relative_to(project_root):
        raise ValueError('目标超出项目目录')
    template=Path(template or TEMPLATE)
    with project_lock(root):
        data=root/'data/project.json'
        if not data.resolve().is_relative_to(root.resolve()):
            raise ValueError('工程数据超出项目目录')
        existing=data.exists()
        if existing:
            validate(json.loads(data.read_text(encoding='utf-8-sig')),root/'server.py' if (root/'server.py').exists() else template/'server.py')
            project=None
        else:
            plan=json.loads(Path(plan_path).read_text(encoding='utf-8-sig')) if plan_path else None
            project=build_project(title or (plan or {}).get('title') or project_root.name,plan)
            validate(project,template/'server.py')
        for source in template.rglob('*'):
            if source.is_dir() or '__pycache__' in source.parts:
                continue
            target=root/source.relative_to(template)
            if not target.resolve().is_relative_to(root.resolve()):
                raise ValueError('目标文件超出工程目录')
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,target)
        if project is not None:
            atomic_json(data,project)
        result=dict(projectRoot=str(project_root),dataFile=str(data),created=not existing,version='1.2.0')
        if launch:
            result.update(start(root,port))
        return result

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='action',required=True)
    command=sub.add_parser('ensure')
    command.add_argument('--project-root',required=True)
    command.add_argument('--title')
    command.add_argument('--plan',type=Path)
    command.add_argument('--start',action='store_true')
    command.add_argument('--port',type=int)
    args=parser.parse_args()
    try:
        print(json.dumps(ensure(args.project_root,args.title,args.plan,args.start,args.port),ensure_ascii=False))
    except Exception as error:
        print(json.dumps(dict(error=str(error)),ensure_ascii=False),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
