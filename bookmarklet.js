// lexilog capture bookmarklet (readable source).
// Select a word or phrase on any page, click the bookmark, and lexilog opens
// with the word, its sentence, the page title, link and language filled in.
(function () {
  var APP = "http://localhost:8501/add";
  var sel = window.getSelection();
  var text = sel.toString().trim();
  if (!text) { alert("Select a word or phrase first."); return; }

  // Grow the selection to the surrounding sentence.
  var block = sel.anchorNode && sel.anchorNode.parentElement;
  while (block && block.innerText && block.innerText.length < text.length + 20 && block.parentElement) {
    block = block.parentElement;
  }
  var para = (block && block.innerText) || text;
  var i = para.indexOf(text), sentence = text;
  if (i >= 0) {
    var start = Math.max(para.lastIndexOf(". ", i), para.lastIndexOf("! ", i),
                         para.lastIndexOf("? ", i), para.lastIndexOf("\n", i));
    var ends = [". ", "! ", "? ", "\n"].map(function (p) { return para.indexOf(p, i + text.length); })
                                       .filter(function (n) { return n >= 0; });
    var end = ends.length ? Math.min.apply(null, ends) + 1 : para.length;
    sentence = para.slice(start < 0 ? 0 : start + 1, end).trim();
  }

  var lang = (document.documentElement.lang || "").slice(0, 2).toLowerCase();
  var host = location.hostname;
  var source = /youtube/.test(host) ? "youtube" : /duolingo/.test(host) ? "duolingo" : "news";
  var q = new URLSearchParams({ text: text, sentence: sentence, url: location.href,
                                title: document.title, lang: lang, source: source });
  window.open(APP + "?" + q.toString(), "lexilog");
})();
