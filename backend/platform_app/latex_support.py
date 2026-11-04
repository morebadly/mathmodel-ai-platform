"""Small, deterministic TeX input assistance; execution stays in the remote sandbox."""
import re

VERSION='body-math-assist-v1'
PACKAGES={'amsmath':r'\\(?:dfrac|tfrac|text|substack|binom|overset|underset|operatorname|eqref|begin\{(?:align(?:at|ed(?:at)?)?|flalign|gather(?:ed)?|multline(?:d)?|cases|smallmatrix|[pbBvV]?matrix|split)\*?\})',
          'amssymb':r'\\(?:mathbb|mathfrak|leqslant|geqslant)', 'bm':r'\\bm\b',
          'graphicx':r'\\includegraphics\b','booktabs':r'\\(?:toprule|midrule|bottomrule)\b'}
MATH_ENVS=r'(?:equation|align|alignat|flalign|aligned|alignedat|gather|gathered|multline|multlined|displaymath|math|eqnarray|split|smallmatrix|[pbBvV]?matrix|[dr]?cases|array|subarray|CD)\*?'
BARE_START=re.compile(r'^(?:\\(?:[dt]?frac|sqrt|sum|prod|int|iint|lim|mathbb|mathbf|bm|vec)\b|[A-Za-z](?:_\{[^}]+\}|_[A-Za-z0-9])?\s*=)')

def without_comment(line):
    for index,char in enumerate(line):
        if char!='%':continue
        cursor=index-1
        while cursor>=0 and line[cursor]=='\\':cursor-=1
        if (index-1-cursor)%2==0:return line[:index]
    return line

def prepare(source):
    code=source.replace('\r\n','\n').replace('\r','\n').lstrip('\ufeff');offset=0;notes=[]
    fenced=re.fullmatch(r'\s*```(?:latex|tex)?[ \t]*\n([\s\S]*?)\n```\s*',code,re.I)
    if fenced:
        offset=-code[:fenced.start(1)].count('\n');code=fenced.group(1);notes.append('已去掉包在整份源码外的 Markdown 代码围栏；原稿保留。')
    lines=[];math=False;environment_depth=0;verbatim=False
    for number,line in enumerate(code.split('\n'),1):
        stripped=without_comment(line).strip()
        if re.search(r'\\begin\{(?:verbatim\*?|lstlisting|minted)\}',stripped):verbatim=True
        if not verbatim:
            # Assist only a complete, standalone, ASCII math expression. Do not
            # guess the meaning of prose containing a formula or incomplete input.
            if (not math and not environment_depth and BARE_START.match(stripped)
                and not re.search(r'(?<!\\)\$|\\[\[\]()\]]|[^\x00-\x7f]',stripped)
                and stripped.count('{')==stripped.count('}') and len(stripped)<=5000):
                line=line.replace(stripped,r'\[ '+stripped+r' \]',1)
                if len(notes)<12:notes.append('第'+str(number-offset)+'行独立公式已补齐数学环境；原稿保留。')
                stripped=r'\[ '+stripped+r' \]'
            tokens=re.findall(r'\\(?:begin\{'+MATH_ENVS+r'\}|end\{'+MATH_ENVS+r'\}|\[|\]|\(|\))|(?<!\\)\$\$?',stripped)
            for token in tokens:
                if token.startswith('\\begin'):environment_depth+=1
                elif token.startswith('\\end'):environment_depth=max(0,environment_depth-1)
                elif token in [r'\[',r'\(']:math=True
                elif token in [r'\]',r'\)']:math=False
                else:math=not math
        lines.append(line)
        if re.search(r'\\end\{(?:verbatim\*?|lstlisting|minted)\}',stripped):verbatim=False
    code='\n'.join(lines)
    # Preserve indices so inserted packages cannot accidentally land in a comment
    # containing a fake begin{document}; multiline class/package options are valid.
    inspect='\n'.join(without_comment(line)+' '*(len(line)-len(without_comment(line))) for line in code.split('\n'))
    blank=lambda match:re.sub(r'[^\n]',' ',match[0])
    inspect=re.sub(r'\\begin\{(?:verbatim\*?|lstlisting|minted)\}[\s\S]*?\\end\{(?:verbatim\*?|lstlisting|minted)\}',blank,inspect)
    inspect=re.sub(r'\\verb\*?([^A-Za-z0-9\s])(?:(?!\1)[^\n])*\1',blank,inspect)
    full=bool(re.search(r'\\documentclass\s*(?:\[[\s\S]*?\]\s*)?\{',inspect))
    if not full:
        prefix=r'\documentclass[UTF8,fontset=none]{ctexart}\setCJKmainfont{Noto Serif CJK SC}\setCJKsansfont{Noto Sans CJK SC}\usepackage{amsmath,amssymb,mathtools,bm,graphicx,booktabs,longtable,array}\begin{document}'
        code=prefix+'\n'+code+'\n'+r'\end{document}';offset+=1;notes.insert(0,'正文模式：已补齐中文文档模板及常用数学宏包；原稿保留。')
    else:
        loaded={name.strip() for group in re.findall(r'\\(?:usepackage|RequirePackage)\s*(?:\[[\s\S]*?\]\s*)?\{([^}]+)\}',inspect) for name in group.split(',')}
        missing=[name for name,pattern in PACKAGES.items() if name not in loaded and re.search(pattern,inspect) and not (name in ['amssymb','bm'] and 'unicode-math' in loaded)]
        begin=re.search(r'\\begin\{document\}',inspect)
        if missing and begin:
            code=code[:begin.start()]+r'\usepackage{'+','.join(missing)+'}'+code[begin.start():]
            notes.insert(0,'已按使用的命令补齐宏包：'+', '.join(missing)+'；原稿保留。')
    return code,offset,notes

def diagnostics(log,source):
    _,offset,_=prepare(source);result=[]
    for match in re.finditer(r'(?:\./)?(?:main\.tex|input/[^\n:]+):([0-9]+):\s*([^\n]+)',log):
        line=max(1,int(match[1])-offset);message=match[2].strip();hint='请检查该行命令、括号及对应宏包。'
        if 'Missing $' in message:hint=r'公式需要数学环境。可选中公式后点“行间公式”，或使用 $...$、\(...\)、\[...\]。'
        elif 'Undefined control' in message:hint='命令未定义，请检查拼写或在完整源码的导言区加载对应宏包。'
        elif 'not found' in message or 'cannot be found' in message:hint='检查文件是否已作为编译附件选入、引用路径是否正确，或改用模板中已提供的字体。'
        result.append({'line':line,'message':message[:220],'hint':hint})
        if len(result)>=5:break
    if not result:
        error=next((line.strip('! ') for line in log.splitlines() if line.startswith('!') or 'LaTeX Error' in line or 'Package fontspec Error' in line),None)
        if error:result.append({'line':None,'message':error[:220],'hint':'查看下方完整日志；缺少的模板文件或字体需要另外提供。'})
    return result
