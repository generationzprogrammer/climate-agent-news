/* Dependency-free Word, PDF and chart export. Charts use validated evidence values. */
(() => {
  "use strict";
  const utf8 = new TextEncoder();
  const xml = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"}[c]));
  const save = (blob, name) => {const url = URL.createObjectURL(blob), a = document.createElement("a"); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);};
  function chartSvg(chart) {
    const points = chart.points || [], max = Math.max(1, ...points.map(p => p.value)), min = Math.min(0, ...points.map(p => p.value));
    const scale = v => 240 + (v - min) / (max - min) * 540;
    const title = chart.title.length > 32 ? chart.title.slice(0, 32) + "…" : chart.title;
    const sourceLabel = points.slice(0, 5).map(p => `[${p.id}]`).join(" ") + (points.length > 5 ? " 等，详见参考资料" : "");
    const height = 150 + points.length * 46;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 ${height}" role="img" aria-label="${xml(chart.title)}" style="font-family:Arial,'Microsoft YaHei',sans-serif;background:white"><rect width="960" height="${height}" fill="white"/><text x="24" y="36" font-size="24" fill="#111">${xml(title)}</text><text x="24" y="66" font-size="17" fill="#555">单位：${xml(chart.unit)}</text>${points.map((p, i) => `<text x="24" y="${108 + i * 46}" font-size="17">${xml(p.label)}</text><rect x="${scale(Math.min(0, p.value))}" y="${88 + i * 46}" width="${Math.abs(scale(p.value) - scale(0))}" height="26" fill="#267269"/><text x="${scale(Math.max(0, p.value)) + 10}" y="${108 + i * 46}" font-size="17">${xml(p.value)}</text>`).join("")}<text x="24" y="${height - 22}" font-size="15" fill="#555">${xml(sourceLabel)}</text></svg>`;
  }
  async function chartCanvas(chart) {
    const svg = chartSvg(chart), img = new Image();
    const url = URL.createObjectURL(new Blob([svg], {type: "image/svg+xml"}));
    try {await new Promise((resolve, reject) => {img.onload = resolve; img.onerror = reject; img.src = url;});
      const canvas = document.createElement("canvas"); canvas.width = 1920; canvas.height = (150 + chart.points.length * 46) * 2;
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height); return canvas;
    } finally {URL.revokeObjectURL(url);}
  }
  function reportParts(result) {
    const title = result.report?.title || "京津冀绿色转型分析";
    const sections = result.report?.sections?.length ? result.report.sections : [{heading: "分析", paragraphs: result.answer.split(/\n\s*\n/)}];
    const parts = [{text: title, type: "title"}, {text: `日期：${String(result.generated_at || new Date().toISOString()).slice(0, 10)}`, type: "meta"}];
    sections.forEach(s => {parts.push({text: s.heading, type: "heading"}); s.paragraphs.forEach(p => parts.push({text: p, type: "body"}));});
    result.charts.forEach(c => parts.push({chart: c, type: "chart"}));
    parts.push({text: "参考资料", type: "heading"});
    result.sources.forEach(s => {
      const numeric = s.kind === "observation" ? `；${s.region}，${s.year}年，${s.value} ${s.unit}；${s.locator || ""}；${s.status || ""}${s.notes ? "；" + s.notes : ""}` : `；${s.region}；${s.date}`;
      parts.push({text: `[${s.id}] ${s.title}。${s.source}${numeric}。${s.url}`, type: "source"});
    });
    return {title, parts};
  }
  // Minimal ZIP with STORE compression and CRC32; produces real Office Open XML.
  const crcTable = Uint32Array.from({length: 256}, (_, i) => {let n = i; for (let k = 0; k < 8; k++) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1; return n;});
  const crc = data => {let n = 0xffffffff; for (const x of data) n = crcTable[(n ^ x) & 255] ^ (n >>> 8); return (n ^ 0xffffffff) >>> 0;};
  function zip(files) {
    const local = [], central = []; let offset = 0, centralSize = 0;
    for (const [name, content] of Object.entries(files)) {
      const filename = utf8.encode(name), data = typeof content === "string" ? utf8.encode(content) : content, hash = crc(data);
      const h = new Uint8Array(30), v = new DataView(h.buffer); v.setUint32(0, 0x04034b50, true); v.setUint16(4, 20, true); v.setUint32(14, hash, true); v.setUint32(18, data.length, true); v.setUint32(22, data.length, true); v.setUint16(26, filename.length, true);
      local.push(h, filename, data);
      const c = new Uint8Array(46), cv = new DataView(c.buffer); cv.setUint32(0, 0x02014b50, true); cv.setUint16(4, 20, true); cv.setUint16(6, 20, true); cv.setUint32(16, hash, true); cv.setUint32(20, data.length, true); cv.setUint32(24, data.length, true); cv.setUint16(28, filename.length, true); cv.setUint32(42, offset, true);
      central.push(c, filename); centralSize += c.length + filename.length; offset += h.length + filename.length + data.length;
    }
    const end = new Uint8Array(22), ev = new DataView(end.buffer); ev.setUint32(0, 0x06054b50, true); ev.setUint16(8, central.length / 2, true); ev.setUint16(10, central.length / 2, true); ev.setUint32(12, centralSize, true); ev.setUint32(16, offset, true);
    return new Blob([...local, ...central, end], {type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"});
  }
  async function docx(result) {
    const {parts} = reportParts(result), images = {}, relationships = []; let imageCount = 0;
    const body = [];
    for (const part of parts) {
      if (part.chart) {
        const canvas = await chartCanvas(part.chart), blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
        const n = ++imageCount, cx = 5486400, cy = Math.round(cx * canvas.height / canvas.width);
        images[`word/media/chart${n}.png`] = new Uint8Array(await blob.arrayBuffer());
        relationships.push(`<Relationship Id="rId${n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/chart${n}.png"/>`);
        body.push(`<w:p><w:r><w:drawing><wp:inline><wp:extent cx="${cx}" cy="${cy}"/><wp:docPr id="${n}" name="图${n}" descr="${xml(part.chart.title)}"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="${n}" name="chart${n}.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rId${n}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>`);
      } else {
        const size = part.type === "title" ? 34 : part.type === "heading" ? 28 : part.type === "source" ? 20 : 24;
        const bold = ["title", "heading"].includes(part.type), style = part.type === "title" ? "Title" : part.type === "heading" ? "Heading1" : "Normal";
        body.push(`<w:p><w:pPr><w:pStyle w:val="${style}"/>${bold ? '<w:keepNext/>' : ""}<w:spacing w:after="160" w:line="360" w:lineRule="auto"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/><w:color w:val="000000"/><w:sz w:val="${size}"/>${bold ? '<w:b/>' : ""}</w:rPr><w:t xml:space="preserve">${xml(part.text)}</w:t></w:r></w:p>`);
      }
    }
    const files = {
      "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>',
      "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
      "word/styles.xml": '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style></w:styles>',
      "word/_rels/document.xml.rels": `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${relationships.join("")}<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`,
      "word/document.xml": `<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>${body.join("")}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1200" w:bottom="1200" w:left="1440" w:right="1440"/></w:sectPr></w:body></w:document>`,
      ...images,
    };
    return zip(files);
  }
  async function pdf(result) {
    // Page images preserve Chinese glyphs without a third-party font download.
    const pages = [], width = 1654, height = 2339, margin = 130; let canvas, ctx, y;
    function newPage() {canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height; ctx = canvas.getContext("2d"); ctx.fillStyle = "white"; ctx.fillRect(0, 0, width, height); ctx.fillStyle = "black"; y = margin; pages.push(canvas);}
    newPage();
    for (const part of reportParts(result).parts) {
      if (part.chart) {const image = await chartCanvas(part.chart), h = (width - 2 * margin) * image.height / image.width;
        if (y + h > height - margin) newPage(); ctx.drawImage(image, margin, y, width - 2 * margin, h); y += h + 30; continue;}
      const size = part.type === "title" ? 44 : part.type === "heading" ? 34 : part.type === "source" ? 24 : 30, lineHeight = size * 1.65;
      const setFont = () => {ctx.font = `${["title", "heading"].includes(part.type) ? "bold " : ""}${size}px "Times New Roman",SimSun,"Noto Serif CJK SC",serif`;};
      setFont(); let line = ""; const lines = [];
      for (const char of Array.from(part.text || "")) {if (char === "\n" || ctx.measureText(line + char).width > width - 2 * margin) {lines.push(line); line = char === "\n" ? "" : char;} else line += char;}
      if (line) lines.push(line);
      if (part.type === "heading" && y + lineHeight * 3 > height - margin) {newPage(); setFont();}
      for (const value of lines) {if (y + lineHeight > height - margin) {newPage(); setFont();} ctx.fillText(value, margin, y + size); y += lineHeight;}
      y += 24;
    }
    const data = pages.map((p, i) => {const context = p.getContext("2d"); context.font = '22px "Times New Roman",serif'; context.fillText(String(i + 1), width / 2, height - 65); return Uint8Array.from(atob(p.toDataURL("image/jpeg", 0.93).split(",")[1]), c => c.charCodeAt(0));});
    const objects = [null, "<< /Type /Catalog /Pages 2 0 R >>", `<< /Type /Pages /Count ${pages.length} /Kids [${pages.map((_, i) => `${3 + i * 3} 0 R`).join(" ")}] >>`];
    for (let i = 0; i < data.length; i++) {
      const n = 3 + i * 3, commands = `q 595.28 0 0 841.89 0 0 cm /Im${i} Do Q`;
      objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Resources << /XObject << /Im${i} ${n + 1} 0 R >> >> /Contents ${n + 2} 0 R >>`);
      objects.push([utf8.encode(`<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${data[i].length} >>\nstream\n`), data[i], utf8.encode("\nendstream")]);
      objects.push(`<< /Length ${commands.length} >>\nstream\n${commands}\nendstream`);
    }
    const chunks = [utf8.encode("%PDF-1.4\n")], offsets = [0]; let total = chunks[0].length;
    for (let i = 1; i < objects.length; i++) {offsets.push(total); const head = utf8.encode(`${i} 0 obj\n`), tail = utf8.encode("\nendobj\n"), content = typeof objects[i] === "string" ? [utf8.encode(objects[i])] : objects[i]; chunks.push(head, ...content, tail); total += head.length + tail.length + content.reduce((n, x) => n + x.length, 0);}
    chunks.push(utf8.encode(`xref\n0 ${objects.length}\n0000000000 65535 f \n${offsets.slice(1).map(x => String(x).padStart(10, "0") + " 00000 n \n").join("")}trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${total}\n%%EOF`));
    return new Blob(chunks, {type: "application/pdf"});
  }
  async function download(result, format, chartIndex = 0) {
    const filename = reportParts(result).title.replace(/[<>:"/\\|?*]/g, "").slice(0, 70) || "京津冀分析";
    if (format === "png") {const chart = result.charts[chartIndex], canvas = await chartCanvas(chart); save(await new Promise(resolve => canvas.toBlob(resolve, "image/png")), `${chart.title}.png`);}
    else if (format === "docx") save(await docx(result), `${filename}.docx`);
    else if (format === "pdf") save(await pdf(result), `${filename}.pdf`);
  }
  window.GruenBthReport = {chartSvg, download, docx, pdf, reportParts};
})();
