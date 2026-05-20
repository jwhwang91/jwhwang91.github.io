# E2E GUI System Architecture HTML Template

Use this template when generating a new single-file technical architecture HTML page in the same style as `_Projects/E2E_GUI_SystemArchitecture.html`.

## Style Identity

- Build a dense, dark, engineering-focused architecture document, not a marketing page.
- Use one self-contained HTML file with embedded `<style>` and `<script>`.
- Prefer Korean labels when the source/domain content is Korean, but keep technical identifiers, filenames, function names, and protocol names in English.
- Overall feel: compact, source-based, diagnostic, diagram-heavy.
- Primary audience: engineers reading system structure, data flow, file responsibilities, and implementation details.

## Page Structure

Use this order:

1. `<!DOCTYPE html>` with `<html lang="ko">`.
2. `<head>` containing UTF-8 metadata, responsive viewport, title, and full embedded CSS.
3. Fixed top `<nav>` with brand plus section anchors.
4. `.hero` containing:
   - `.hero-pill` for product/platform category.
   - Large gradient `<h1>`.
   - One compact summary paragraph.
5. `.page` wrapper containing numbered `<section class="section" id="sN">` blocks.
6. Footer with source/platform summary.
7. Shared modal markup.
8. Inline script with modal data object and open/close handlers.

## Visual System

### Color Tokens

Use CSS custom properties and keep this palette:

```css
:root{
  --bg:#0a0a0f;--bg2:#111118;--bg3:#1a1a24;--bg4:#22222f;--surface:#16161f;
  --border:#2a2a3a;--border2:#333348;
  --text-pri:#f0f0f5;--text-sec:#9898b0;--text-ter:#5a5a72;
  --accent:#3b82f6;--accent2:#60a5fa;
  --green:#34d399;--green-d:#0d4a32;
  --red:#f87171;--red-d:#4a0d0d;
  --orange:#fb923c;--orange-d:#4a2a0d;
  --purple:#a78bfa;--purple-d:#2d1a4a;
  --yellow:#fbbf24;--yellow-d:#4a3a0a;
  --cyan:#22d3ee;--cyan-d:#0a3a4a;
}
```

### Typography

- Body font: `-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',sans-serif`.
- Code font: `'SF Mono','Fira Code',monospace`.
- Body line-height: `1.6`.
- Section titles: 21px, 700, slight negative letter spacing.
- Card copy: 12.5px, muted color, line-height 1.65.
- Tables: 12.5px body, 10.5px uppercase headers.

### Layout Rules

- Fixed nav height: 50px.
- Hero top padding: about 110px to clear nav.
- Main page width: `max-width:1240px`, centered, horizontal padding 24px.
- Section bottom spacing: 60px.
- Cards use 12px radius; callouts/tables use 10px radius; modal uses 16px radius.
- Responsive grids collapse:
  - Desktop: `.grid-2`, `.grid-3`, `.grid-4`.
  - Under 900px: 2 columns.
  - Under 600px: 1 column.

## Required Components

### Fixed Navigation

Pattern:

```html
<nav>
  <span class="nav-brand">PROJECT NAME</span>
  <a href="#s1">개요</a>
  <a href="#s2">아키텍처</a>
  <a href="#s3">Backend</a>
</nav>
```

Behavior/style:

- `position:fixed; top:0; left:0; right:0; z-index:100`
- Dark translucent background with `backdrop-filter:blur(24px)`.
- Small compact links, hover background `--bg4`.

### Hero

Pattern:

```html
<div class="hero">
  <div class="hero-pill">Platform / Domain Tag</div>
  <h1>Project Name<br>System Architecture</h1>
  <p>One sentence summary of hardware, runtime, data path, IPC, models, and UI.</p>
</div>
```

Style:

- Center aligned.
- Radial blue glow via `.hero::before`.
- H1 gradient text from `#f0f0f5` to `--accent2` to `--cyan`.

### Numbered Section Header

Pattern:

```html
<section class="section" id="s1">
  <div class="section-header">
    <div class="section-num">1</div>
    <h2>Section Title</h2>
  </div>
</section>
```

Use one section per major architecture topic.

### Callouts

Pattern:

```html
<div class="callout cl-info">
  <div class="callout-icon">💡</div>
  <div class="callout-body">
    <strong>Main point</strong>
    Explanation text with technical keywords and code references.
  </div>
</div>
```

Variants:

- `.cl-info`: blue, general notes.
- `.cl-ok`: green, validated behavior or optimization.
- `.cl-warn`: orange, caveat or operational warning.
- `.cl-danger`: red, failure mode or critical issue.
- `.cl-purple`: purple, architecture highlight.

### Statistic Row

Pattern:

```html
<div class="stat-row">
  <div class="stat-card">
    <div class="s-val" style="color:var(--cyan)">CAN-FD</div>
    <div class="s-lbl">2 Mbps data phase</div>
  </div>
</div>
```

Use for key constraints, sizes, rates, counts, buffer sizes, and protocols.

### Cards

Pattern:

```html
<div class="card" onclick="openModal('component_id')" style="border-color:#3b82f6">
  <div class="card-label"><span class="logo-badge lb-py">Python</span> module.py</div>
  <h3>Component Name</h3>
  <ul>
    <li><code>function_name()</code> — concise responsibility</li>
    <li>Important implementation detail</li>
  </ul>
</div>
```

Use cards for modules, subsystems, files, known issues, and functional groups.

Rules:

- Card hover should subtly lift and brighten.
- Use clickable cards when a modal has deeper source/function detail.
- Keep card text compact and specific.

### Badges

Use `.badge` for status, numbered flow steps, risk labels, and timing choices:

```html
<span class="badge b-green">OK</span>
<span class="badge b-blue">1</span>
<span class="badge b-purple">SHM</span>
```

Use `.logo-badge` for technology/file labels:

```html
<span class="logo-badge lb-cpp">C++</span>
<span class="logo-badge lb-py">Python</span>
<span class="logo-badge lb-onnx">ONNX</span>
```

### Highlight Box

Pattern:

```html
<div class="hl-box">
  <h4>Important Detail</h4>
  <p>Short explanation with <code>code</code> identifiers.</p>
</div>
```

Use after diagrams/screenshots to explain what the reader is seeing.

### Tables

Pattern:

```html
<div class="tbl-wrap">
  <table>
    <thead>
      <tr><th>Step</th><th>From</th><th>To</th><th>API / Mechanism</th><th>File</th></tr>
    </thead>
    <tbody>
      <tr><td><span class="badge b-blue">1</span></td><td>A</td><td>B</td><td><code>call()</code></td><td>file.cpp</td></tr>
    </tbody>
  </table>
</div>
```

Use tables for:

- Data flow.
- Timing parameters.
- Known issues and fixes.
- Memory layouts.
- File responsibility maps.

### Diagram Containers

Use `.svg-wrap` for architecture diagrams and memory maps:

```html
<div class="svg-wrap">
  <div class="svg-title">System Architecture</div>
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
    <!-- grouped clickable blocks -->
    <g class="iblock" onclick="openModal('component_id')">
      <rect x="40" y="40" width="180" height="80" rx="8" fill="#1a1a3a" stroke="#3b82f6"/>
      <text x="130" y="82" text-anchor="middle" fill="#f0f0f5" font-size="13" font-weight="700">Component</text>
    </g>
  </svg>
</div>
```

Diagram conventions:

- Dark background `#111118`.
- Use colored swimlanes or grouped regions for hardware, C++ backend, Python backend, frontend, models, utility, and IPC.
- Use arrows with `<marker>` definitions.
- Use `.iblock` on clickable SVG groups.
- Keep text inside SVG small and precise.
- Use `filter:brightness(1.2)` on hover through `.iblock:hover`.

### Embedded Screenshot/Image

Pattern:

```html
<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;padding:4px">
  <img src="data:image/jpeg;base64,..." alt="Main screen"
       style="width:100%;border-radius:10px;display:block;height:auto;"
       onerror="this.parentElement.innerHTML='<div style=\'padding:36px;text-align:center;color:var(--text-ter);font-size:13px\'>Image missing</div>'"/>
</div>
```

Use inline base64 only when the document must remain fully self-contained.

### Modal System

Shared modal markup:

```html
<div class="modal-overlay" id="modal" onclick="closeModal(event)">
  <div class="modal-box">
    <button class="modal-close" onclick="closeModal()">닫기</button>
    <div class="modal-tag" id="m-tag"></div>
    <div class="modal-title" id="m-title"></div>
    <div class="modal-body" id="m-body"></div>
  </div>
</div>
```

Script pattern:

```html
<script>
const M = {
  component_id:{
    tag:'Category',
    title:'Component Title',
    body:`
      <h4>Key Functions</h4>
      <div class="fn-row">
        <div class="fn-item">
          <div class="fn-sig">function_name(args) → result</div>
          <div class="fn-desc">What it does and why it matters.</div>
        </div>
      </div>
    `
  }
};

function openModal(id){
  const m=M[id];if(!m)return;
  document.getElementById('m-tag').textContent=m.tag;
  document.getElementById('m-title').textContent=m.title;
  document.getElementById('m-body').innerHTML=m.body;
  document.getElementById('modal').classList.add('active');
}
function closeModal(e){
  if(!e||e.target.id==='modal'||e.currentTarget.classList?.contains('modal-close'))
    document.getElementById('modal').classList.remove('active');
}
document.addEventListener('keydown',e=>{
  if(e.key==='Escape')document.getElementById('modal').classList.remove('active');
});
</script>
```

Modal body conventions:

- Use `<h4>` sections.
- Use `.fn-row`, `.fn-item`, `.fn-sig`, `.fn-desc` for functions.
- Use `.file-list`, `.file-item`, `.fname`, `.fdesc` for file-level details.
- Use `<pre>` for protocol payloads, structs, JSON config, or pseudo-code.

## Recommended Section Blueprint

For architecture documents, use this section sequence:

1. **System Overview**
   - One purple callout explaining the system purpose.
   - Stat row of protocol, payload size, memory size, model runtime, cycle time, or limits.
   - Main UI screenshot or top-level conceptual image.
   - Two cards: hardware and software stack.

2. **Full Architecture Diagram**
   - Info callout telling readers that blocks are clickable.
   - Large inline SVG diagram.
   - Legend for colors/arrows if needed.

3. **Backend Detail**
   - Grid of source-file cards.
   - Each card opens a modal with functions and failure modes.
   - Add timing/protocol table if relevant.

4. **Runtime / IPC Detail**
   - Memory map SVG or table.
   - Struct definitions in highlight boxes or modals.
   - Seqlock, queue, buffer, or threading notes.

5. **Frontend Detail**
   - UI/controller cards.
   - Event and rendering behavior.
   - Plot/monitor performance notes if relevant.

6. **Utility / Parsing / Build Tools**
   - Parser, converter, DAG/builder, or build cards.

7. **Real-Time Data Flow**
   - Table with numbered steps, From, To, API/Mechanism, File.
   - OK/warn callouts for optimizations and known timing issues.

8. **File Structure**
   - Two-column cards for major language/source trees.
   - Known issues and fixes table at the end.

## Content Writing Rules

- Every card should answer: file/component, role, key functions, important constraints.
- Avoid generic descriptions like "handles logic"; name exact functions, protocols, buffers, commands, or thread loops.
- Keep bullets short. One technical fact per bullet.
- Use `<code>` for filenames, functions, constants, IDs, offsets, payloads, and commands.
- Prefer tables when comparing repeated items.
- Prefer SVG diagrams when explaining relationships or memory layout.
- Put detailed function signatures in modals, not in the main page body.

## Starter HTML Skeleton

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{{PROJECT_NAME}} — System Architecture</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0a0f;--bg2:#111118;--bg3:#1a1a24;--bg4:#22222f;--surface:#16161f;
  --border:#2a2a3a;--border2:#333348;
  --text-pri:#f0f0f5;--text-sec:#9898b0;--text-ter:#5a5a72;
  --accent:#3b82f6;--accent2:#60a5fa;
  --green:#34d399;--green-d:#0d4a32;--red:#f87171;--red-d:#4a0d0d;
  --orange:#fb923c;--orange-d:#4a2a0d;--purple:#a78bfa;--purple-d:#2d1a4a;
  --yellow:#fbbf24;--yellow-d:#4a3a0a;--cyan:#22d3ee;--cyan-d:#0a3a4a;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text-pri);font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',sans-serif;line-height:1.6}
nav{position:fixed;top:0;left:0;right:0;z-index:100;display:flex;align-items:center;gap:3px;padding:0 20px;height:50px;background:rgba(10,10,15,.9);backdrop-filter:blur(24px);border-bottom:1px solid var(--border);flex-wrap:wrap}
.nav-brand{font-weight:700;font-size:14px;color:var(--accent2);margin-right:12px;white-space:nowrap}
nav a{color:var(--text-sec);text-decoration:none;font-size:11.5px;padding:4px 8px;border-radius:6px;transition:.2s;white-space:nowrap}
nav a:hover{background:var(--bg4);color:var(--text-pri)}
.hero{padding:110px 24px 50px;text-align:center;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:0;left:50%;transform:translateX(-50%);width:900px;height:420px;background:radial-gradient(ellipse at 50% 0%,rgba(59,130,246,.16) 0%,transparent 70%);pointer-events:none}
.hero-pill{display:inline-block;background:rgba(59,130,246,.15);border:1px solid rgba(59,130,246,.4);color:var(--accent2);font-size:11px;font-weight:600;padding:4px 14px;border-radius:20px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:18px}
.hero h1{font-size:clamp(26px,4.5vw,50px);font-weight:800;letter-spacing:-.03em;background:linear-gradient(135deg,#f0f0f5 0%,#60a5fa 50%,#22d3ee 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1.15;margin-bottom:14px}
.hero p{color:var(--text-sec);font-size:14px;max-width:720px;margin:0 auto}
.page{max-width:1240px;margin:0 auto;padding:0 24px 80px}
.section{margin-bottom:60px}
.section-header{display:flex;align-items:center;gap:14px;margin-bottom:24px}
.section-num{width:30px;height:30px;background:var(--accent);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex-shrink:0}
.section-header h2{font-size:21px;font-weight:700;letter-spacing:-.02em}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px 22px;transition:.2s;cursor:pointer;position:relative;overflow:hidden}
.card::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(59,130,246,.03) 0%,transparent 60%);pointer-events:none}
.card:hover{background:var(--bg4);border-color:var(--border2);transform:translateY(-1px)}
.card-label{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent2);margin-bottom:7px}
.card h3{font-size:14px;font-weight:700;margin-bottom:7px}
.card p,.card ul{font-size:12.5px;color:var(--text-sec);line-height:1.65}
.card ul{padding-left:15px}.card li{margin-bottom:2px}
.card code,.modal-body code{background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:1px 5px;font-size:11px;color:var(--cyan);font-family:'SF Mono','Fira Code',monospace}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
@media(max-width:900px){.grid-2,.grid-3,.grid-4{grid-template-columns:1fr 1fr}}
@media(max-width:600px){.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}}
.callout{display:flex;gap:12px;padding:14px 16px;border-radius:10px;border-left:3px solid;margin:14px 0}
.callout-icon{font-size:17px;flex-shrink:0;margin-top:1px}.callout-body{font-size:12.5px;line-height:1.65}.callout-body strong{display:block;margin-bottom:3px;font-size:13px}
.cl-info{background:rgba(59,130,246,.08);border-color:var(--accent)}.cl-ok{background:rgba(52,211,153,.08);border-color:var(--green)}.cl-warn{background:rgba(251,146,60,.08);border-color:var(--orange)}.cl-danger{background:rgba(248,113,113,.08);border-color:var(--red)}.cl-purple{background:rgba(167,139,250,.08);border-color:var(--purple)}
.badge{display:inline-block;font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px}.b-green{background:var(--green-d);color:var(--green)}.b-red{background:var(--red-d);color:var(--red)}.b-blue{background:rgba(59,130,246,.18);color:var(--accent2)}.b-orange{background:var(--orange-d);color:var(--orange)}.b-purple{background:var(--purple-d);color:var(--purple)}.b-yellow{background:var(--yellow-d);color:var(--yellow)}.b-cyan{background:var(--cyan-d);color:var(--cyan)}
.svg-wrap{background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:22px;overflow-x:auto}.svg-title{font-size:12px;font-weight:700;color:var(--text-sec);letter-spacing:.06em;text-transform:uppercase;margin-bottom:16px}
.stat-row{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;flex:1;min-width:110px;text-align:center}.s-val{font-size:22px;font-weight:800;color:var(--accent2)}.s-lbl{font-size:10.5px;color:var(--text-ter);margin-top:3px}
.hl-box{background:var(--bg3);border:1px solid var(--border2);border-radius:10px;padding:16px 18px;margin:14px 0}.hl-box h4{font-size:12.5px;font-weight:700;margin-bottom:7px;color:var(--accent2)}.hl-box p{font-size:12.5px;color:var(--text-sec);line-height:1.65}
.tbl-wrap{overflow-x:auto;border-radius:10px;border:1px solid var(--border)}table{width:100%;border-collapse:collapse;font-size:12.5px}th{background:var(--bg3);color:var(--text-sec);font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:9px 13px;text-align:left;border-bottom:1px solid var(--border)}td{padding:9px 13px;border-bottom:1px solid var(--border);color:var(--text-pri)}tr:last-child td{border-bottom:none}tr:hover td{background:var(--bg4)}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:200;align-items:center;justify-content:center;backdrop-filter:blur(5px)}.modal-overlay.active{display:flex}.modal-box{background:var(--surface);border:1px solid var(--border2);border-radius:16px;padding:28px;max-width:580px;width:92%;max-height:82vh;overflow-y:auto;position:relative;animation:mIn .2s ease}@keyframes mIn{from{opacity:0;transform:translateY(10px) scale(.97)}to{opacity:1;transform:none}}.modal-close{position:absolute;top:14px;right:16px;background:var(--bg4);border:1px solid var(--border);color:var(--text-sec);cursor:pointer;border-radius:7px;padding:3px 9px;font-size:12px;transition:.2s}.modal-close:hover{background:var(--border2);color:var(--text-pri)}.modal-tag{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);margin-bottom:8px}.modal-title{font-size:18px;font-weight:800;margin-bottom:14px;letter-spacing:-.02em}.modal-body{font-size:13px;color:var(--text-sec);line-height:1.75}.modal-body h4{color:var(--text-pri);font-size:13px;margin:14px 0 5px;font-weight:700}.modal-body ul{padding-left:16px;margin-bottom:8px}.modal-body pre{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:12px;font-size:11px;color:var(--text-sec);overflow-x:auto;line-height:1.6;font-family:'SF Mono','Fira Code',monospace;margin:8px 0}
.file-list{display:flex;flex-direction:column;gap:7px;margin-top:7px}.file-item{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:9px 13px}.file-item .fname{color:var(--accent2);font-weight:700;font-size:12px;font-family:'SF Mono','Fira Code',monospace;margin-bottom:4px}.file-item .fdesc{color:var(--text-sec);font-size:12px;line-height:1.55}
.fn-row{display:flex;flex-direction:column;gap:5px;margin-top:5px}.fn-item{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:6px 10px;font-size:11px}.fn-item .fn-sig{color:var(--yellow);font-family:'SF Mono','Fira Code',monospace;font-size:10.5px;margin-bottom:2px}.fn-item .fn-desc{color:var(--text-sec)}
.logo-badge{display:inline-flex;align-items:center;gap:4px;background:var(--bg3);border:1px solid var(--border);border-radius:5px;padding:2px 8px;font-size:10.5px;font-weight:700;margin:2px}.lb-cpp{color:#659ad2}.lb-py{color:#ffd43b}.lb-vec{color:#e8364e}.lb-onnx{color:#67b346}
.iblock{cursor:pointer;transition:filter .15s}.iblock:hover{filter:brightness(1.2)}
footer{text-align:center;padding:28px 24px;border-top:1px solid var(--border);color:var(--text-ter);font-size:11.5px;line-height:1.9}
</style>
</head>
<body>
<nav>
  <span class="nav-brand">{{SHORT_NAME}}</span>
  <a href="#s1">개요</a>
  <a href="#s2">아키텍처</a>
  <a href="#s3">상세</a>
</nav>

<div class="hero">
  <div class="hero-pill">{{DOMAIN_TAG}}</div>
  <h1>{{PROJECT_NAME}}<br>System Architecture</h1>
  <p>{{ONE_SENTENCE_SYSTEM_SUMMARY}}</p>
</div>

<div class="page">
  <section class="section" id="s1">
    <div class="section-header"><div class="section-num">1</div><h2>시스템 개요</h2></div>
    <div class="callout cl-purple">
      <div class="callout-icon">◆</div>
      <div class="callout-body"><strong>{{KEY_ARCHITECTURE_POINT}}</strong>{{SUMMARY_DETAIL}}</div>
    </div>
    <div class="stat-row">
      <div class="stat-card"><div class="s-val" style="color:var(--cyan)">{{STAT_VALUE}}</div><div class="s-lbl">{{STAT_LABEL}}</div></div>
    </div>
  </section>

  <section class="section" id="s2">
    <div class="section-header"><div class="section-num">2</div><h2>전체 아키텍처</h2></div>
    <div class="callout cl-info">
      <div class="callout-icon">i</div>
      <div class="callout-body"><strong>블록 클릭 → 상세 팝업</strong> 함수, 파일, 데이터 흐름을 모달로 정리한다.</div>
    </div>
    <div class="svg-wrap">
      <div class="svg-title">{{DIAGRAM_TITLE}}</div>
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 360" width="960" height="360" style="max-width:100%;height:auto;display:block">
        <rect width="960" height="360" fill="#111118"/>
      </svg>
    </div>
  </section>
</div>

<footer>
  {{PROJECT_NAME}} · Source-based Architecture Doc · Dark Theme · Inline SVG
</footer>

<div class="modal-overlay" id="modal" onclick="closeModal(event)">
  <div class="modal-box">
    <button class="modal-close" onclick="closeModal()">닫기</button>
    <div class="modal-tag" id="m-tag"></div>
    <div class="modal-title" id="m-title"></div>
    <div class="modal-body" id="m-body"></div>
  </div>
</div>

<script>
const M = {};
function openModal(id){const m=M[id];if(!m)return;document.getElementById('m-tag').textContent=m.tag;document.getElementById('m-title').textContent=m.title;document.getElementById('m-body').innerHTML=m.body;document.getElementById('modal').classList.add('active');}
function closeModal(e){if(!e||e.target.id==='modal'||e.currentTarget.classList?.contains('modal-close'))document.getElementById('modal').classList.remove('active');}
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.getElementById('modal').classList.remove('active');});
</script>
</body>
</html>
```

## Generation Checklist

- Nav links match every section ID.
- Section numbers are sequential.
- Every clickable `onclick="openModal('id')"` has a matching `M.id` entry.
- Tables fit in `.tbl-wrap`.
- SVG uses `max-width:100%;height:auto`.
- Important source files and functions are written with `<code>` or modal `.fn-sig`.
- Footer summarizes the platform and document type.
- The output remains a single standalone HTML file unless the user explicitly asks for external assets.
