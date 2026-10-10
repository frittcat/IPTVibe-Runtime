"""Record synchronization provenance and code review needs without exposing origin secrets."""
import argparse,datetime,json,os,subprocess,urllib.request
from pathlib import Path

def github(path):
    headers={'Accept':'application/vnd.github+json','User-Agent':'IPTVibe-upstream-review'}
    if os.environ.get('GH_TOKEN'):headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/'+path,headers=headers),timeout=30) as response:return json.load(response)

def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    config=json.loads(Path('upstream-review.json').read_text())
    release=github('repos/'+config['releaseRepository']+'/releases/latest')
    commit=github('repos/'+config['androidRepository']+'/commits?per_page=1')[0]
    comparison=github('repos/'+config['androidRepository']+'/compare/'+config['androidReviewedCommit']+'...'+commit['sha'])
    state={'schema':1,'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'catalogCommit':subprocess.check_output(['git','-C',args.upstream,'rev-parse','HEAD'],text=True).strip(),
           'application':{'latestRelease':release['tag_name'],'releaseUrl':release['html_url'],
             'androidCommit':commit['sha'],'reviewedCommit':config['androidReviewedCommit'],
             'reviewRequired':comparison.get('ahead_by',0)>0,
             'changedFiles':[v['filename'] for v in comparison.get('files',[])]},'policy':config['policy']}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    summary='Upstream release '+release['tag_name']+'; application adaptation required: '+str(state['application']['reviewRequired'])
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write(summary+'\n')
if __name__=='__main__':main()
