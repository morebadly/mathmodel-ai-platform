"""Build the optional E2B TeX image using the existing account; never run user TeX locally."""
import argparse,os
from pathlib import Path
from dotenv import load_dotenv
from e2b import Template

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='mathmodel-xelatex-v1');parser.add_argument('--env-file',type=Path)
    args=parser.parse_args()
    if args.env_file:load_dotenv(args.env_file,override=False)
    secret_path=os.getenv('E2B_API_KEY_FILE');api_key=Path(secret_path).read_text().strip() if secret_path else os.getenv('E2B_API_KEY','')
    if not api_key:raise SystemExit('Set E2B_API_KEY_FILE or E2B_API_KEY in backend-only configuration.')
    template=(Template().from_template('code-interpreter-v1')
        .run_cmd("find /etc/apt -name '*.list' -o -name '*.sources' | xargs -r sed -i 's|http://deb.debian.org|https://deb.debian.org|g; s|http://security.debian.org|https://security.debian.org|g'",user='root')
        .run_cmd('apt-get -o Acquire::Retries=3 update && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 install -y --no-install-recommends texlive-xetex texlive-lang-chinese texlive-latex-extra fonts-noto-cjk poppler-utils',user='root')
        .run_cmd('DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 install -y --no-install-recommends latexmk biber texlive-bibtex-extra',user='root')
        .run_cmd('xelatex --version | head -n 1; latexmk -v | head -n 2; biber --version; kpsewhich ctexart.cls; fc-match "Noto Serif CJK SC"'))
    result=Template.build(template,alias=args.name,cpu_count=2,memory_mb=2048,api_key=api_key)
    print('Template ready:',result.template_id)
    print('Set E2B_LATEX_TEMPLATE='+args.name+' in the web and execution worker environments.')

if __name__=='__main__':main()
