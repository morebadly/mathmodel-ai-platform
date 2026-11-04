/* Shared safe Markdown/math display. This is a preview, never a PDF compiler. */
'use strict';
window.MMRichText=(()=>{
 let parser;
 function markdown(text){
  if(!parser){parser=window.markdownit({html:false,linkify:true,breaks:true});parser.use(window.texmath,{engine:window.katex,delimiters:['dollars','brackets','beg_end'],katexOptions:{throwOnError:false,trust:false,maxExpand:1000}});
   // texmath's bracket display rule only starts a new block. A formula directly
   // after prose also needs an inline fallback, before Markdown escapes its slash.
   parser.inline.ruler.before('escape','mm_bracket_display',(state,silent)=>{
    if(!state.src.startsWith('\\[',state.pos))return false;
    const end=state.src.indexOf('\\]',state.pos+2);if(end<0)return false;
    if(!silent){const token=state.push('mm_bracket_display','math',0);token.content=state.src.slice(state.pos+2,end);}
    state.pos=end+2;return true;
   });
   parser.renderer.rules.mm_bracket_display=(tokens,index)=>window.texmath.render(tokens[index].content,true,{throwOnError:false,trust:false,maxExpand:1000});
  }
  return window.DOMPurify.sanitize(parser.render(String(text||'')),{USE_PROFILES:{html:true,mathMl:true,svg:true},FORBID_TAGS:['style','script','iframe','object','embed'],ADD_ATTR:['target']});
 }
 function texPreview(source){
  let text=String(source||''),body=text.match(/\\begin\{document\}([\s\S]*?)\\end\{document\}/);if(body)text=body[1];
  // Protect math before translating a small set of prose commands for instant
  // display. The complete source is compiled separately by XeLaTeX.
  let marker='MMFORMULAPREVIEW';while(text.includes(marker))marker+='X';const math=[];
  text=text.replace(/\$\$[\s\S]*?\$\$|\$(?:\\.|[^$\n])+\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\\begin\{(align\*?|equation\*?|gather\*?|multline\*?)\}[\s\S]*?\\end\{\1\}/g,value=>marker+(math.push(value)-1)+'END');
  text=text.replace(/^\s*(\\(?:[dt]?frac|sqrt|sum|prod|int|iint|lim|mathbb|mathbf|bm|vec)\b[^\n]*)$/gm,(line,formula)=>{if(formula.includes(marker)||formula.includes('$')||/[^\x00-\x7f]/.test(formula)||formula.split('{').length!==formula.split('}').length)return line;return '\n'+marker+(math.push('\\[ '+formula+' \\]')-1)+'END\n';});
  text=text.replace(/\\(?:subsubsection|subsection|section)\*?\{([^{}]*)\}/g,(value,title)=>'\n\n'+(value.startsWith('\\subsub')?'### ':value.startsWith('\\sub')?'## ':'# ')+title+'\n\n')
   .replace(/\\textbf\{([^{}]*)\}/g,'**$1**').replace(/\\(?:emph|textit)\{([^{}]*)\}/g,'*$1*')
   .replace(/\\begin\{(?:itemize|enumerate|abstract)\}|\\end\{(?:itemize|enumerate|abstract)\}/g,'\n')
   .replace(/\\item\b\s*/g,'\n- ').replace(/\\(?:maketitle|tableofcontents)\b/g,'').replace(/\\(?:newpage|clearpage)\b/g,'\n\n---\n\n')
   .replace(/\\([%&_#{}])/g,'$1');
  text=text.replace(new RegExp(marker+'(\\d+)END','g'),(_,n)=>math[Number(n)]);
  const limited=text.length>40000;return markdown(text.slice(0,40000))+(limited?'<p>即时预览仅展示前4万字符，完整内容请查看编译PDF。</p>':'');
 }
 return {markdown,texPreview};
})();
