// Parser regression only. DOMPurify and final DOM are verified in the browser.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.join(__dirname,'..');
const window={markdownit:require('../vendor/markdown-it/dist/markdown-it.min.js'),texmath:require('../vendor/texmath/texmath.js'),katex:require('../vendor/katex/katex.min.js'),DOMPurify:{sanitize:html=>html}};
vm.runInNewContext(fs.readFileSync(path.join(root,'rich-text.js'),'utf8'),{window});
const renderer=window.MMRichText;
for(const source of ['Formula \\(x^2\\).','Formula \\[ \\frac{a}{b} \\]','Formula $x^2$.','Formula $$x^2$$.'])assert.match(renderer.markdown(source),/class="katex/);
assert.match(renderer.texPreview('\\section{正文}\n\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}'),/class="katex/);
assert.match(renderer.markdown('## 标题\n**加粗**'),/<h2>标题<\/h2>\s*<p><strong>加粗<\/strong>/);
assert.doesNotMatch(renderer.markdown('`\\(x\\)`'),/class="katex/);
assert.doesNotMatch(renderer.markdown('```tex\n\\[x\\]\n```'),/class="katex/);
assert.doesNotMatch(renderer.markdown('<img src=x onerror=alert(1)>'),/<img/);
assert.doesNotMatch(renderer.markdown('[link](javascript:alert(1))'),/href="javascript:/);
assert.doesNotThrow(()=>renderer.markdown('Formula \\[ '+'{'.repeat(3000)+'x'+'}'.repeat(3000)+' \\]'));
console.log('Rich text parser: delimiters, code protection, Markdown, unsafe raw HTML/links and pathological input passed.');
