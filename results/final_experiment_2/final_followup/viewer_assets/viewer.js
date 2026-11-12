/* MathHint static reader. Original strings remain in the JSON payload and raw panels. */
(function () {
  'use strict';
  var data;
  try { data = JSON.parse(document.getElementById('viewer-data').textContent); }
  catch (error) { document.getElementById('status').textContent = '저장된 읽기 자료를 불러오지 못했습니다.'; return; }
  var questions = data.questions || [];
  var byId = new Map(questions.map(function (q) { return [q.id, q]; }));
  var repeatControl=document.getElementById('repeat-select');
  var methods = data.methods || [{key:'baseline',label:'A 문제만'}, {key:'regression_hint',label:'B 예측 해설 토큰'}, {key:'oracle_hint',label:'C 실제 해설 토큰'}];
  var search = document.getElementById('search');
  var filter = document.getElementById('filter');var taxonomyFields=['curriculum','unit','subunit','type'];var taxonomy=taxonomyFields.map(function(k){return document.getElementById('field-'+k);});taxonomyFields.forEach(function(k,i){var values=Array.from(new Set(questions.map(function(q){return(q.metadata||{})[k];}).filter(Boolean))).sort();values.forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;taxonomy[i].append(o);});});
  var select = document.getElementById('question-select');
  var status = document.getElementById('status');
  var content = document.getElementById('question-content');
  var currentId = null;
  var visible = questions;
  var md = window.markdownit ? window.markdownit({html:false, linkify:false, typographer:false, breaks:true}) : null;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function escaped(text) { return md ? md.utils.escapeHtml(String(text)) : String(text).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function slashEscaped(src, pos) { var count = 0; while (pos > 0 && src[--pos] === '\\') count++; return count % 2 === 1; }
  function closeAt(src, closing, start) {
    var pos = src.indexOf(closing, start);
    while (pos >= 0) { if (!slashEscaped(src, pos)) return pos; pos = src.indexOf(closing, pos + closing.length); }
    return -1;
  }
  function mathHTML(tex, display, original, failure) {
    var classes = 'math-expression' + (display ? ' math-display' : '');
    if (!failure && window.katex) {
      try {
        return '<span class="' + classes + '" data-math-rendered="true">' + window.katex.renderToString(tex, {
          displayMode:display, throwOnError:true, trust:false, strict:'warn',
          maxExpand:1000, maxSize:20, macros:{}, output:'htmlAndMathml'
        }) + '</span>';
      } catch (error) { failure = error.message || '수식 해석 오류'; }
    }
    if (!failure) failure = '로컬 수식 표시 파일을 불러오지 못했습니다.';
    return '<span class="' + classes + ' math-error" data-render-error="true"><span class="render-error-label">수식 표시 실패 · 원문</span><code>' + escaped(original) + '</code><span class="render-error-reason">' + escaped(failure) + '</span></span>';
  }
  if (md) {
    md.renderer.rules.table_open = function () { return '<div class="table-scroll"><table>'; };
    md.renderer.rules.table_close = function () { return '</table></div>'; };
    md.renderer.rules.image = function (tokens, idx) { return '<span class="external-image">[이미지: ' + escaped(tokens[idx].content || '원문 보기') + ' · 자동 로드하지 않음]</span>'; };
    var oldLink = md.renderer.rules.link_open || function (tokens, idx, opts, env, renderer) { return renderer.renderToken(tokens,idx,opts); };
    md.renderer.rules.link_open = function (tokens, idx, opts, env, renderer) { tokens[idx].attrSet('rel','noopener noreferrer'); tokens[idx].attrSet('target','_blank'); return oldLink(tokens,idx,opts,env,renderer); };
  }
  var renderSequence = 0;
  function protectMath(text) {
    // Markdown block maps identify code accurately, including indented/nested code.
    // Opaque math placeholders protect table pipes, underscores and backslashes.
    var offsets=[0],ranges=[],tokens=md.parse(text,{});
    for(var j=0;j<text.length;j++)if(text[j]==='\n')offsets.push(j+1);
    tokens.forEach(function(t){if((t.type==='fence'||t.type==='code_block')&&t.map)ranges.push([offsets[t.map[0]],offsets[t.map[1]]===undefined?text.length:offsets[t.map[1]]]);});
    ranges.sort(function(a,b){return a[0]-b[0];});
    var prefix='MATHHINT'+Date.now().toString(36)+'X'+(++renderSequence)+'X',items=[],parts=[],i=0,rangeIndex=0;
    while(i<text.length){
      while(rangeIndex<ranges.length&&ranges[rangeIndex][1]<=i)rangeIndex++;
      var range=ranges[rangeIndex];
      if(range&&i>=range[0]&&i<range[1]){parts.push(text.slice(i,range[1]));i=range[1];continue;}
      if(text[i]==='`'&&!slashEscaped(text,i)){
        var count=1;while(text[i+count]==='`')count++;
        var needle='`'.repeat(count),position=i+count,found=-1;
        while((position=text.indexOf(needle,position))>=0){var n=count;while(text[position+n]==='`')n++;if(n===count){found=position;break;}position+=n;}
        if(found>=0){parts.push(text.slice(i,found+count));i=found+count;continue;}
      }
      var opening=null,closing=null,display=false;
      if(!slashEscaped(text,i)){
        if(text.startsWith('\\(',i)){opening='\\(';closing='\\)';}
        else if(text.startsWith('\\[',i)){opening='\\[';closing='\\]';display=true;}
        else if(text.startsWith('$$',i)){opening=closing='$$';display=true;}
        else if(text[i]==='$'){opening=closing='$';}
      }
      if(!opening){parts.push(text[i++]);continue;}
      var close=closeAt(text,closing,i+opening.length),end=close<0?text.indexOf('\n',i):close+closing.length;
      if(end<0)end=text.length;
      var original=text.slice(i,end),tex=close<0?original:text.slice(i+opening.length,close),marker=prefix+items.length+'END';
      items.push({marker:marker,tex:tex,original:original,display:display,failure:close<0?'닫히지 않은 수식 구분자':null});parts.push(marker);i=end;
    }
    return {text:parts.join(''),items:items};
  }
  function renderMarkdown(text) {
    var node = el('div','rendered-markdown');
    if (!md) { node.append(el('p','render-error-label','Markdown 표시 파일이 없어 원문을 표시합니다.'),el('pre','',text || '')); return node; }
    try {
      var protectedText=protectMath(String(text||''));node.innerHTML=md.render(protectedText.text);
      // Restore only text nodes. A placeholder in a link URL can never inject HTML.
      var walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),leaves=[],leaf;
      while((leaf=walker.nextNode()))if(!leaf.parentElement.closest('pre,code'))leaves.push(leaf);
      leaves.forEach(function(originalNode){
        var value=originalNode.nodeValue,matched=protectedText.items.filter(function(t){return value.includes(t.marker);});if(!matched.length)return;
        var frag=document.createDocumentFragment(),position=0;
        while(position<value.length){var next=null,at=value.length;matched.forEach(function(t){var p=value.indexOf(t.marker,position);if(p>=0&&p<at){next=t;at=p;}});frag.append(document.createTextNode(value.slice(position,at)));if(!next)break;
          var template=document.createElement('template');template.innerHTML=mathHTML(next.tex,next.display,next.original,next.failure);frag.append(template.content);position=at+next.marker.length;
        }
        originalNode.replaceWith(frag);
      });
      node.querySelectorAll('a').forEach(function(anchor){
        ['href','title'].forEach(function(attribute){
          var original=anchor.getAttribute(attribute);if(original===null)return;
          var restored=original;protectedText.items.forEach(function(item){restored=restored.split(item.marker).join(item.original);});
          if(attribute==='title'){anchor.setAttribute(attribute,restored);return;}
          var normalized=md.normalizeLink(restored);
          try {var target=new URL(normalized,location.href);if(!md.validateLink(normalized)||!['http:','https:','file:','mailto:','tel:'].includes(target.protocol))throw Error('unsupported');anchor.setAttribute(attribute,normalized);}
          catch(_){anchor.removeAttribute(attribute);}
        });
      });
    } catch (error) { node.replaceChildren(el('p','render-error-label','표시 실패 · 원문'),el('pre','',text || '')); }
    return node;
  }
  function fmt(value) { return value === null || value === undefined ? '미제공' : String(value); }
  function rawPanel(title, text) { var section = el('section','raw-section'); section.append(el('h5','',title),el('pre','',text)); return section; }
  function disclosure(label, className) { var d = el('details',className); d.append(el('summary','',label)); return d; }
  function rawOriginals(row, method) {
    var d = disclosure('원문 보기 · 시스템 지시 / 실제 입력 / 응답 / 사용량 / 해시','raw-originals'); d.dataset.method = method;
    d.append(rawPanel('시스템 지시문',row.system_instruction || ''),rawPanel(row.status==='not_run'?'저장된 전송 예정 입력 · API 미실행':'실제 사용자 입력',row.input_text || ''),rawPanel('응답 원문',row.output_text || ''));
    d.append(rawPanel('사용량 · 미제공 값은 null',JSON.stringify(row.usage || {},null,2)),rawPanel('입력·응답 식별 정보',JSON.stringify({input_sha256:row.input_sha256,output_sha256:row.output_sha256,response_sha256:row.response_sha256,display_output_sha256:row.display_output_sha256,config_id:row.config_id,response_id:row.response_id,model:row.model,model_version:row.model_version,thinking_level:row.thinking_level,status:row.status},null,2)));
    d.append(rawPanel('모델·생성 설정',JSON.stringify({requested_model:row.model,returned_model_version:row.model_version,thinking_level:row.thinking_level,temperature:(data.config||{}).temperature,max_output_tokens:(data.config||{}).max_output_tokens},null,2)),rawPanel('실행 당시 출처 기록 · 과거 경로 포함',JSON.stringify(row.provenance||{},null,2)));
    d.append(rawPanel('반복·원본 자동채점·표시용 판정',JSON.stringify({repeat:row.repeat,request_id:row.request_id,request_sha256:row.request_sha256,evaluation_raw:row.evaluation_raw,grade_source:row.grade_source,api_response_received:row.api_received,finish_reasons:row.finish_reasons,response_origin:row.response_origin},null,2)),rawPanel('동결 SDK 요청 인자',JSON.stringify(row.sdk_request||{},null,2)),rawPanel('동결 원천·모델·어휘 해시와 원본 정답',JSON.stringify(row.frozen_source_audit||{},null,2)),rawPanel('새 응답 풀이 검토 원문',JSON.stringify(row.review||{},null,2)));return d;
  }
  function conditionStatus(row, expected) {
    if (!expected) return {label:'생성 실험 대상 아님',kind:'not-applicable'};
    if (!row || row.status==='not_run') return {label:'API 미실행',kind:'not-run'};
    if (row.status !== 'success') return {label:row.status === 'api_error' ? 'API 실패' : row.status && row.status.includes('truncated') ? '응답 잘림 · 채점 보류' : '실행 중단 / 실패: ' + row.status,kind:'api-error'};
    var value = row.evaluation && row.evaluation.correct;
    if (value === true) return {label:'정답',kind:'correct'};
    if (value === false) return {label:'오답',kind:'incorrect'};
    return {label:'채점 불가',kind:'ungraded'};
  }
  function safeLink(href, label) {
    var a = el('a','',label);
    try { var url = new URL(href,location.href); if (!['file:','http:','https:'].includes(url.protocol)) throw Error('unsupported'); a.href = href; a.rel = 'noopener noreferrer'; }
    catch (_) { return el('span','',label); }
    return a;
  }
  function reviewPanel(row) {
    var review = row.review;
    var panel = el('div','review-panel');
    if (!review || !review.math_status) { panel.append(el('span','muted','풀이 검토: 미검토 / 검토 보류')); return panel; }
    var labels = {appropriate:'타당 가능 · 보조 검토',inappropriate:'오류 의심 · 보조 검토',uncertain:'검토 보류'};
    panel.append(el('p','', '풀이 검토: ' + (labels[review.math_status] || '판단 보류') + ' · ' + (review.human_confirmed === true ? '사람 확인' : review.reviewer_type==='not_reviewed' ? '아직 검토하지 않음' : 'AI 보조 · 사람 미확정')));
    if (review.reason) { var details = disclosure('풀이 검토 근거'); details.append(renderMarkdown(review.reason)); panel.append(details); }
    return panel;
  }
  function appendDataTables(q, article) {
    if (q.regression) {
      var d = disclosure('이 문항의 실제·예측 빈도와 회귀 지표','regression-details');
      var r = q.regression;
      d.append(el('p','', 'MSE ' + fmt(r.clipped_nonnegative_mse) + ' · MAE ' + fmt(r.clipped_nonnegative_mae) + ' · 코사인 ' + fmt(r.clipped_nonnegative_cosine_similarity)));
      var actual, predicted;
      try { actual = typeof r.actual_top20 === 'string' ? JSON.parse(r.actual_top20) : r.actual_top20; predicted = typeof r.predicted_top20 === 'string' ? JSON.parse(r.predicted_top20) : r.predicted_top20; } catch (_) {}
      if (actual && predicted) {
        var wrap = el('div','table-scroll'),table = el('table'),head = el('tr'); ['순위','실제 상위 토큰','실제 빈도','예측 상위 토큰','예측 빈도'].forEach(function(t){head.append(el('th','',t));});var thead=el('thead');thead.append(head);table.append(thead);var body=el('tbody');
        for(var i=0;i<Math.max(actual.length,predicted.length);i++){var tr=el('tr');[i+1,actual[i]&&actual[i].token,actual[i]&&actual[i].frequency,predicted[i]&&predicted[i].token,predicted[i]&&predicted[i].frequency].forEach(function(t){tr.append(el('td','',t===undefined?'—':t));});body.append(tr);}table.append(body);wrap.append(table);d.append(wrap);
      }
      article.append(d);
    }
    if (q.clusters && q.clusters.length) {
      var group = disclosure('이 문항의 군집 배정','cluster-details');
      q.clusters.forEach(function (r) { group.append(el('p','', [r.level,r.method,'군집 '+r.cluster,r.actual_label].filter(Boolean).join(' · '))); }); article.append(group);
    }
  }
  function showQuestion(id, updateHash) {
    var q = byId.get(id); if (!q) return false;
    currentId = id; content.replaceChildren(); select.value = id;
    var article = el('article','question');article.id='question-'+q.id;article.dataset.id=q.id;
    var meta = q.metadata || {};
    article.append(el('h2','question-title',q.id),el('p','metadata',[q.split==='train'?'학습':'테스트',meta.curriculum,meta.unit,meta.subunit,meta.type].filter(Boolean).join(' · ')));
    if(meta.source)article.append(el('p','source','출처: '+meta.source));if(q.split==='train'&&q.expected_generation)article.append(el('p','notice','학습 문항의 반복 실험: 모델 학습에 사용된 문항의 결과이며 일반화 성능이 아닙니다.'));
    var problem=el('section','problem');problem.append(el('h3','','문제'),renderMarkdown(q.problem_text || ''));article.append(problem);
    var rawProblem=disclosure('문제 원문 보기','raw-problem');rawProblem.append(el('pre','',q.problem_text||''));if(q.problem_href)rawProblem.append(safeLink(q.problem_href,'문제 TXT 원본'));article.append(rawProblem);
    var reference=disclosure('원본 정답·해설 전체','reference');reference.open=true;reference.append(renderMarkdown('원본 정답: '+fmt(q.reference_answer)),renderMarkdown(q.reference_solution||''));var rr=disclosure('정답·해설 원문 보기');rr.append(el('pre','',q.reference_solution||''));if(q.solution_href)rr.append(safeLink(q.solution_href,'해설 TXT 원본'));reference.append(rr);article.append(reference);
    if(q.answer_key_conflict)article.append(el('p','notice','원본 정답표 충돌 의심 · 기존 AI 보조 근거, 사람 미확정. 정답표 충돌 문항: 원본 답과 AI 보조 검토 답을 구분합니다. AI 보조 답: '+fmt(q.ai_supplemental_answer)));
    if(!q.expected_generation){article.append(el('p','notice not-applicable','생성 실험 대상 아님 · 학습 문항입니다. 추가 API 호출이나 응답 누락이 아닙니다.'));}
    else {
      article.append(el('p','muted','정오답은 정정 정답표와 새 응답의 독립 검토 기준입니다. 원본 자동채점은 원문 감사에 보존합니다. 풀이 검토와 AI 보조 정답표 평가는 별도로 표시합니다. D/F는 같은 실제 해설 토큰의 오라클 진단이며 출처 제목만 다릅니다. E는 지시문만 추가합니다. 정답과 풀이 검토는 별개입니다.'));
      var grid=el('div','conditions');
      methods.filter(function(method){return(q.available_conditions||[]).includes(method.condition);}).forEach(function (method) {
        var row=(q.conditions||{})[method.key], state=conditionStatus(row,true), card=el('section','condition-card');card.dataset.method=method.key;
        card.append(el('h3','',method.label+' · 반복 '+repeatControl.value),el('span','badge '+state.kind,state.label));
        if(row){var usage=row.usage||{};card.append(el('p','token-usage','입력 '+fmt(usage.prompt_token_count)+' · 출력 '+fmt(usage.candidates_token_count)+' · 추론 '+fmt(usage.thoughts_token_count)+' · 전체 '+fmt(usage.total_token_count)));
          if(row.hint){var hints=disclosure(row.status==='not_run'?'전송 예정 힌트 · API 미실행':'실제 요청 힌트 · token: frequency');hints.append(rawPanel('전송 JSON',JSON.stringify(row.hint.mapping||{},null,2)));card.append(hints);}if(row.grade_source==='independent_new_AI_answer_review')card.append(el('p','notice','자동 판정과 구분해 이 새 응답의 구체 근거로 최종 답을 따로 검토했습니다. 원본 판정은 아래 감사에 보존합니다.'));if(row.evaluation&&row.evaluation.predicted_answer!==undefined)card.append(el('p','final-answer','판독한 최종 답: '+fmt(row.evaluation.predicted_answer)));
          if(q.answer_key_conflict&&typeof row.correct_ai_supplemental==='boolean')card.append(el('p','notice','AI 보조 정답표 기준: '+(row.correct_ai_supplemental?'정답':'오답')+' · 사람의 확정 판정 아님'));
          if(row.status==='success'&&row.output_text)card.append(renderMarkdown(row.output_text));else if(row.output_text)card.append(renderMarkdown(row.output_text));
          if(row.error){var error=typeof row.error==='object'?JSON.stringify(row.error,null,2):String(row.error);card.append(el('pre','api-error-detail',error));}
          card.append(reviewPanel(row),rawOriginals(row,method.key));
        }else card.append(el('p','muted','저장된 API 응답이 없습니다. 읽기 화면은 추가 요청을 보내지 않습니다.'));
        grid.append(card);
      });var comparison=el('div','comparison-layout');reference.remove();comparison.append(reference,grid);article.append(comparison);
    }
    appendDataTables(q,article);
    content.append(article);if(updateHash!==false&&location.hash.slice(1)!==id)history.replaceState(null,'','#'+encodeURIComponent(id));
    return true;
  }
  function qualifies(q, value) {
    var rows=methods.filter(function(m){return(q.available_conditions||[]).includes(m.condition);}).map(function(m){return(q.conditions||{})[m.key];});
    if(value==='control_scope')return q.is_control;if(value==='error_scope')return q.is_error_repeat;if(value==='train')return q.split==='train';if(value==='test')return q.split==='test';if(value==='answers')return q.changed_answers;if(value==='review')return q.reasoning_suspected||q.review_pending;if(['A_correct_B_wrong','A_correct_C_wrong','B_only_correct','C_only_correct','D_only_correct','all_wrong','D_wrong','answer_key_conflict','reasoning_suspected','possible_alternative','large_token_change','incomplete'].includes(value))return(q.case_tags||[]).includes(value);
    if(value==='changed')return q.expected_generation&&q.changed_correctness===true;
    if(value==='api_error')return q.expected_generation&&rows.some(function(r){return r&&r.status!=='success'&&r.status!=='not_run';});
    if(value==='not_run')return q.expected_generation&&rows.some(function(r){return !r||r.status==='not_run';});
    if(value==='ungraded')return q.expected_generation&&rows.some(function(r){return r&&r.api_received===true&&typeof(r.evaluation||{}).correct!=='boolean';});
    if(value==='review_pending')return q.expected_generation&&rows.some(function(r){return r&&r.api_received===true&&(!r.review||!r.review.math_status||r.review.math_status==='uncertain');});
    return true;
  }
  function applyFilter(preserve) {
    var term=(search.value||'').trim().toLowerCase(),kind=filter.value;
    visible=questions.filter(function(q){return(q.id+' '+Object.values(q.metadata||{}).join(' ')).toLowerCase().includes(term)&&qualifies(q,kind)&&taxonomyFields.every(function(k,i){return !taxonomy[i].value||(q.metadata||{})[k]===taxonomy[i].value;});});
    select.replaceChildren();visible.forEach(function(q){var o=el('option','',q.id+(q.split==='train'?' · 학습':' · 테스트')+(q.changed_correctness?' · 정오답 변화':''));o.value=q.id;select.append(o);});
    status.textContent=visible.length+' / '+questions.length+'문항 · 테스트 '+(data.test_ids||[]).length+' · 저장된 결과만 읽습니다';
    if(!visible.length){content.replaceChildren(el('p','notice','조건에 맞는 문항이 없습니다.'));currentId=null;return;}
    var wanted=preserve&&visible.some(function(q){return q.id===preserve;})?preserve:visible[0].id;showQuestion(wanted);
  }
  taxonomy.forEach(function(field){field.addEventListener('change',function(){applyFilter(currentId);});});repeatControl.addEventListener('change',function(){questions.forEach(function(q){q.conditions=q.repetitions[String(repeatControl.value)]||{};});applyFilter(currentId);});search.addEventListener('input',function(){applyFilter(currentId);});filter.addEventListener('change',function(){applyFilter(currentId);});select.addEventListener('change',function(){showQuestion(select.value);});
  ['previous','next'].forEach(function(id){var button=document.getElementById(id);if(button)button.addEventListener('click',function(){var i=visible.findIndex(function(q){return q.id===currentId;}),j=i+(id==='previous'?-1:1);if(visible[j])showQuestion(visible[j].id);});});
  window.addEventListener('hashchange',function(){var id=decodeURIComponent(location.hash.slice(1));if(byId.has(id)){search.value='';filter.value='all';taxonomy.forEach(function(f){f.value='';});applyFilter(id);}});
  window.MathHintViewer={renderMarkdown:renderMarkdown,showQuestion:function(id){if(!byId.has(id))return false;search.value='';filter.value='all';taxonomy.forEach(function(f){f.value='';});applyFilter(id);return true;},getCurrentId:function(){return currentId;},getQuestionCount:function(){return questions.length;},setRepeat:function(r){if(!['1','2','3'].includes(String(r)))return false;repeatControl.value=String(r);repeatControl.dispatchEvent(new Event('change'));return true;},getRepeat:function(){return Number(repeatControl.value);}};
  var mainTitle=document.querySelector('header h1');if(mainTitle)mainTitle.after(el('p','experiment-name','실험: '+String(data.experiment_name||'저장 결과')));
  var links=document.getElementById('report-links'),linkLabels={readme:'결과 안내',final_report:'최종 보고서',comparison_csv:'문항별 비교 CSV',raw_responses:'원본 응답 JSONL',regression_csv:'회귀 비교 CSV',clusters_csv:'군집 문항 CSV'};
  if(links)Object.keys(linkLabels).forEach(function(key){if(data.links&&data.links[key])links.append(safeLink(data.links[key],linkLabels[key]));});
  var assetWarning=document.getElementById('asset-warning');if(assetWarning&&md&&window.katex)assetWarning.hidden=true;
  var initial=decodeURIComponent(location.hash.slice(1));if(byId.has(initial))filter.value='all';applyFilter(byId.has(initial)?initial:(questions[0]||{}).id);
  if(!md||!window.katex){var warning=el('p','notice render-error-label','로컬 표시 파일을 불러오지 못했습니다. report.html과 viewer_assets 폴더를 함께 내려받아 여세요.');document.body.insertBefore(warning,document.body.firstChild);}
})();
