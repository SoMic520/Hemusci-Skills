#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

function loadDocx() {
  const candidates = [
    "docx",
    process.env.SOIL_SCIENCE_DOCX_MODULE,
    path.join(os.homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "node_modules", "docx"),
  ].filter(Boolean);
  let lastError;
  for (const candidate of candidates) {
    try { return require(candidate); } catch (error) { lastError = error; }
  }
  throw new Error(`Cannot load the Node docx package. Set SOIL_SCIENCE_DOCX_MODULE. ${lastError || ""}`);
}

const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  Header,
  LevelFormat,
  NumberFormat,
  Packer,
  PageBreak,
  PageNumber,
  Paragraph,
  SectionType,
  ShadingType,
  Table,
  TableCell,
  TableOfContents,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} = loadDocx();

const A4_WIDTH = 11906;
const A4_HEIGHT = 16838;
const MARGINS = { top: 1417, bottom: 1417, left: 1587, right: 1247, header: 850, footer: 850 };
const CONTENT_WIDTH = A4_WIDTH - MARGINS.left - MARGINS.right;
const PLATFORM_BODY_FONT = process.platform === "darwin" ? "STSong" : process.platform === "win32" ? "SimSun" : "Noto Serif CJK SC";
const PLATFORM_HEADING_FONT = process.platform === "darwin" ? "Hiragino Sans GB" : process.platform === "win32" ? "SimHei" : "Noto Sans CJK SC";
const FONT_BODY = process.env.SOIL_BODY_FONT_ZH || PLATFORM_BODY_FONT;
const FONT_HEADING = process.env.SOIL_HEADING_FONT_ZH || PLATFORM_HEADING_FONT;
const FONT_LATIN = "Times New Roman";
const SIZE_HALF_POINTS = {
  "初号": 84, "小初号": 72, "一号": 52, "小一号": 48, "二号": 44, "小二号": 36,
  "三号": 32, "小三号": 30, "四号": 28, "小四号": 24, "五号": 21, "小五号": 18,
  "六号": 15, "小六号": 13, "七号": 11, "八号": 10,
};

function parseArgs(argv) {
  const result = {};
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === "--spec") result.spec = argv[++i];
    else if (argv[i] === "--profiles") result.profiles = argv[++i];
    else if (argv[i] === "--output") result.output = argv[++i];
    else if (argv[i] === "--toc-page-map") result.tocPageMap = argv[++i];
    else throw new Error(`Unknown argument: ${argv[i]}`);
  }
  if (!result.spec || !result.profiles || !result.output) {
    throw new Error("Usage: build_chinese_professional_document.js --spec spec.json --profiles genre-artifact-profiles.json --output output.docx [--toc-page-map map.json]");
  }
  return result;
}

function findRouteAndProfile(spec, registry) {
  if (!registry || registry.schema_version !== 1) throw new Error("artifact profile registry schema_version must be 1");
  const route = (registry.genre_routes || []).find((item) => item.id === spec.genre_profile_id);
  if (!route) throw new Error(`Unknown genre_profile_id: ${spec.genre_profile_id}`);
  const profile = (registry.format_profiles || []).find((item) => item.id === route.format_profile_id);
  if (!profile) throw new Error(`Unknown format profile: ${route.format_profile_id}`);
  return { route, profile };
}

function assertSpec(spec, route, profile) {
  if (!spec || spec.schema_version !== 1) throw new Error("spec.schema_version must be 1");
  if (!["draft", "internal_review", "release"].includes(spec.lifecycle_stage)) throw new Error("spec.lifecycle_stage is invalid");
  if (typeof spec.title !== "string" || !spec.title.trim()) throw new Error("spec.title is required");
  if (!Array.isArray(spec.content) || spec.content.length === 0) throw new Error("spec.content must be a non-empty array");
  if (profile.artifact_kind !== "docx") throw new Error(`Genre ${spec.genre_profile_id} requires ${profile.artifact_kind}, not DOCX`);
  const allowed = new Set(["heading", "paragraph", "bullet_list", "number_list", "table", "notice", "quote", "signature", "page_break"]);
  spec.content.forEach((block, index) => {
    if (!block || !allowed.has(block.type)) throw new Error(`unsupported content block at index ${index}`);
    if (block.type === "heading" && ![1, 2, 3, 4].includes(block.level)) throw new Error(`heading level must be 1-4 at index ${index}`);
    if (["paragraph", "heading", "quote", "signature"].includes(block.type) && typeof block.text !== "string") throw new Error(`text is required at index ${index}`);
    if (["bullet_list", "number_list"].includes(block.type) && (!Array.isArray(block.items) || block.items.length === 0)) throw new Error(`list items are required at index ${index}`);
    if (block.type === "table") {
      if (!Array.isArray(block.headers) || block.headers.length === 0 || !Array.isArray(block.rows)) throw new Error(`invalid table at index ${index}`);
      for (const row of block.rows) if (!Array.isArray(row) || row.length !== block.headers.length) throw new Error(`table row width mismatch at index ${index}`);
      if (block.widths && (block.widths.length !== block.headers.length || block.widths.some((value) => Number(value) <= 0))) throw new Error(`invalid table widths at index ${index}`);
    }
  });
  if (profile.toc_mode === "prohibited" && spec.include_toc) throw new Error(`TOC is prohibited for ${spec.genre_profile_id}`);
  if (profile.toc_mode === "prohibited_unless_controlled_source_requires" && spec.include_toc && spec.controlled_template?.state !== "received_locked") {
    throw new Error(`TOC requires a controlled source for ${spec.genre_profile_id}`);
  }
  if (spec.lifecycle_stage === "release" && route.controlled_template_required_for_release) {
    if (spec.controlled_template?.state !== "received_locked" || !/^[0-9a-fA-F]{64}$/.test(spec.controlled_template?.snapshot_sha256 || "")) {
      throw new Error(`Release for ${spec.genre_profile_id} requires a locked controlled template`);
    }
  }
  if (spec.lifecycle_stage === "release") {
    const roles = new Set(spec.content.map((block) => block.role).filter(Boolean));
    const missing = (route.required_roles || []).filter((role) => !roles.has(role));
    if (missing.length) throw new Error(`Release missing required roles: ${missing.join(", ")}`);
    const serialized = JSON.stringify(spec);
    if (/【待填：[^】]+】/.test(serialized)) throw new Error("Release cannot contain unresolved placeholders");
  }
}

function size(profile, name, fallback) {
  const label = name || fallback;
  const value = SIZE_HALF_POINTS[label];
  if (!value) throw new Error(`Unsupported Chinese size name in profile ${profile.id}: ${label}`);
  return value;
}

function fontConfig(zh = FONT_BODY, latin = FONT_LATIN) {
  return { ascii: latin, hAnsi: latin, eastAsia: zh, cs: latin };
}

function singleFontConfig(name) {
  return { ascii: name, hAnsi: name, eastAsia: name, cs: name };
}

function isCjk(character) {
  return /[\p{Script=Han}\u3000-\u303f\uff00-\uffef，。；：！？、（）【】《》“”‘’—…]/u.test(character);
}

function textRuns(value, options = {}) {
  const children = [];
  String(value ?? "").split("\n").forEach((line, lineIndex) => {
    const segments = [];
    for (const character of line) {
      const kind = isCjk(character) ? "cjk" : "latin";
      const previous = segments[segments.length - 1];
      if (previous && previous.kind === kind) previous.text += character;
      else segments.push({ kind, text: character });
    }
    if (!segments.length) segments.push({ kind: "latin", text: "" });
    segments.forEach((segment, segmentIndex) => {
      const fontName = segment.kind === "cjk" ? (options.zhFont || FONT_BODY) : (options.latinFont || FONT_LATIN);
      children.push(new TextRun({
        text: segment.text,
        font: singleFontConfig(fontName),
        size: options.size,
        bold: Boolean(options.bold),
        italics: Boolean(options.italics),
        color: "000000",
        break: lineIndex > 0 && segmentIndex === 0 ? 1 : undefined,
      }));
    });
  });
  return children;
}

function metrics(profile) {
  const bodySize = size(profile, profile.body_size_zh, "五号");
  return {
    bodySize,
    tableSize: size(profile, profile.table_body_size_zh, "小五号"),
    headings: [1, 2, 3, 4].map((level) => size(profile, profile.heading_sizes_zh[`level_${level}`], level === 1 ? "三号" : "小四号")),
    bodyLine: Math.round(240 * Number(profile.body_line_spacing)),
    firstLine: Math.round(bodySize * 10 * Number(profile.first_line_indent_characters)),
    after: Math.round(240 * Number(profile.paragraph_after_lines)),
  };
}

function bodyParagraph(text, profile, m, options = {}) {
  return new Paragraph({
    children: textRuns(text, { size: options.size || m.bodySize, italics: options.italics }),
    style: "SoilBody",
    alignment: options.alignment || AlignmentType.JUSTIFIED,
    spacing: { line: options.line || m.bodyLine, before: options.before || 0, after: options.after ?? m.after },
    indent: { firstLine: options.noIndent ? 0 : m.firstLine, left: options.left || 0, right: options.right || 0 },
    pageBreakBefore: Boolean(options.pageBreakBefore),
    keepLines: true,
    widowControl: true,
  });
}

function compactParagraph(text, m, options = {}) {
  return new Paragraph({
    children: textRuns(text, { size: options.size || m.tableSize, bold: options.bold, zhFont: options.zhFont }),
    alignment: options.alignment || AlignmentType.LEFT,
    spacing: { line: 240, before: 0, after: 0 },
    indent: { firstLine: 0 },
    keepLines: true,
    widowControl: true,
  });
}

function normalizeWidths(widths, columns) {
  const values = widths && widths.length === columns ? widths.map(Number) : Array(columns).fill(1);
  const total = values.reduce((sum, value) => sum + value, 0);
  const result = values.map((value) => Math.floor((value / total) * CONTENT_WIDTH));
  result[result.length - 1] += CONTENT_WIDTH - result.reduce((sum, value) => sum + value, 0);
  return result;
}

function tableBorders() {
  const edge = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
  return { top: edge, bottom: edge, left: edge, right: edge, insideHorizontal: edge, insideVertical: edge };
}

function tableCell(text, width, m, options = {}) {
  return new TableCell({
    children: [compactParagraph(String(text ?? ""), m, options)],
    width: { size: width, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    shading: { type: ShadingType.CLEAR, fill: "FFFFFF", color: "auto" },
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
  });
}

function dataTable(block, m) {
  const widths = normalizeWidths(block.widths, block.headers.length);
  const rows = [new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: block.headers.map((value, index) => tableCell(value, widths[index], m, { bold: true, zhFont: FONT_HEADING, alignment: AlignmentType.CENTER })),
  })];
  for (const row of block.rows) {
    rows.push(new TableRow({
      cantSplit: true,
      children: row.map((value, index) => tableCell(value, widths[index], m, {
        alignment: (block.center_columns || []).includes(index) ? AlignmentType.CENTER : AlignmentType.LEFT,
      })),
    }));
  }
  const output = [];
  if (block.title) output.push(new Paragraph({
    children: textRuns(block.title, { size: m.bodySize, bold: true, zhFont: FONT_HEADING }),
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 120 },
    keepNext: true,
  }));
  output.push(new Table({ rows, width: { size: CONTENT_WIDTH, type: WidthType.DXA }, columnWidths: widths, borders: tableBorders() }));
  output.push(new Paragraph({ children: [], spacing: { after: 80 } }));
  return output;
}

function titleBlock(spec, profile, m, fullPage) {
  const output = [];
  if (fullPage) output.push(new Paragraph({ children: [], spacing: { after: 1300 } }));
  output.push(new Paragraph({
    children: textRuns(spec.title, { size: fullPage ? 44 : 32, bold: true, zhFont: FONT_HEADING }),
    alignment: AlignmentType.CENTER,
    spacing: { after: spec.subtitle ? 240 : 480 },
    keepLines: true,
  }));
  if (spec.subtitle) output.push(new Paragraph({
    children: textRuns(spec.subtitle, { size: fullPage ? 32 : 24, bold: true, zhFont: FONT_HEADING }),
    alignment: AlignmentType.CENTER,
    spacing: { after: fullPage ? 900 : 360 },
    keepLines: true,
  }));
  for (const item of spec.metadata || []) {
    output.push(new Paragraph({
      children: textRuns(`${item.label}：${item.value}`, { size: fullPage ? 24 : m.bodySize }),
      alignment: AlignmentType.CENTER,
      spacing: { after: fullPage ? 180 : 100 },
      keepLines: true,
    }));
  }
  return output;
}

function headingEntries(spec, tocPageMap) {
  const mapped = Array.isArray(tocPageMap?.entries) ? tocPageMap.entries : [];
  if (!mapped.length) return [];
  return spec.content
    .filter((block) => block.type === "heading")
    .map((block, index) => {
      const match = mapped.find((entry) => entry.index === index && entry.title === block.text)
        || mapped.find((entry) => entry.title === block.text && entry.level === block.level);
      return match && Number.isInteger(match.page)
        ? { title: block.text, level: block.level, page: match.page }
        : null;
    })
    .filter(Boolean);
}

function contentChildren(spec, profile, m, tocPageMap) {
  const children = [];
  let breakBeforeNextBlock = false;
  if (profile.cover_mode === "none") children.push(...titleBlock(spec, profile, m, false));
  if (spec.include_toc) {
    children.push(new Paragraph({
      children: textRuns("目 录", { size: 32, bold: true, zhFont: FONT_HEADING }),
      alignment: AlignmentType.CENTER,
      spacing: { after: 180 },
      keepNext: true,
    }));
    children.push(new TableOfContents("目 录", {
      hyperlink: false,
      headingStyleRange: "1-4",
      cachedEntries: headingEntries(spec, tocPageMap),
      beginDirty: true,
    }));
    // Attach the break to the first body block. A standalone break after a TOC
    // can become an empty page when the updated TOC exactly fills its page.
    breakBeforeNextBlock = true;
  }
  spec.content.forEach((block, blockIndex) => {
    if (block.type === "heading") {
      children.push(new Paragraph({
        children: textRuns(block.text, { size: m.headings[block.level - 1], bold: true, zhFont: FONT_HEADING }),
        style: `SoilHeading${block.level}`,
        pageBreakBefore: Boolean(block.page_break_before || breakBeforeNextBlock),
        spacing: { before: block.level === 1 ? 360 : 240, after: 120 },
        keepNext: true,
        keepLines: true,
      }));
      breakBeforeNextBlock = false;
    } else if (block.type === "paragraph") {
      children.push(bodyParagraph(block.text, profile, m, { noIndent: Boolean(block.no_indent), alignment: block.align === "left" ? AlignmentType.LEFT : AlignmentType.JUSTIFIED, pageBreakBefore: breakBeforeNextBlock }));
      breakBeforeNextBlock = false;
    } else if (block.type === "quote") {
      children.push(bodyParagraph(block.text, profile, m, { noIndent: true, left: 420, right: 420, italics: true, pageBreakBefore: breakBeforeNextBlock }));
      breakBeforeNextBlock = false;
    } else if (block.type === "signature") {
      children.push(bodyParagraph(block.text, profile, m, { noIndent: true, alignment: AlignmentType.RIGHT, before: 240, pageBreakBefore: breakBeforeNextBlock }));
      breakBeforeNextBlock = false;
    } else if (block.type === "notice") {
      children.push(new Paragraph({
        children: textRuns(block.title || "说明", { size: m.headings[2], bold: true, zhFont: FONT_HEADING }),
        pageBreakBefore: breakBeforeNextBlock,
        spacing: { before: 120, after: 120 }, keepNext: true,
      }));
      breakBeforeNextBlock = false;
      children.push(bodyParagraph(block.text || "", profile, m, { noIndent: true }));
    } else if (block.type === "bullet_list" || block.type === "number_list") {
      const reference = block.type === "bullet_list" ? "soil-professional-bullets" : `soil-professional-numbers-${blockIndex}`;
      for (const [itemIndex, item] of block.items.entries()) {
        children.push(new Paragraph({
          children: textRuns(item, { size: m.bodySize }),
          numbering: { reference, level: 0 },
          pageBreakBefore: breakBeforeNextBlock && itemIndex === 0,
          spacing: { line: m.bodyLine, after: m.after },
          keepLines: true,
          widowControl: true,
        }));
      }
      breakBeforeNextBlock = false;
    } else if (block.type === "table") {
      if (breakBeforeNextBlock) children.push(new Paragraph({ children: [], pageBreakBefore: true, spacing: { after: 0 } }));
      breakBeforeNextBlock = false;
      children.push(...dataTable(block, m));
    } else if (block.type === "page_break") {
      if (!breakBeforeNextBlock) children.push(new Paragraph({ children: [new PageBreak()] }));
      breakBeforeNextBlock = false;
    }
  });
  return children;
}

function headerFooter(spec, profile, m) {
  const mode = profile.header_footer_mode;
  const headers = {};
  const footers = {};
  if (!["none_unless_controlled_source_requires", "event_controlled"].includes(mode)) {
    if (["running_header_and_page_number", "document_id_version_and_page_number"].includes(mode)) {
      const headerText = spec.running_header || (mode === "document_id_version_and_page_number" ? `${spec.document_id}｜${spec.title}` : spec.title);
      headers.default = new Header({ children: [new Paragraph({
        children: textRuns(headerText, { size: 15 }), alignment: AlignmentType.CENTER, spacing: { after: 0 },
      })] });
    }
    footers.default = new Footer({ children: [new Paragraph({
      children: [new TextRun({ text: "— ", font: fontConfig(), size: 18 }), new TextRun({ children: [PageNumber.CURRENT], font: fontConfig(), size: 18 }), new TextRun({ text: " —", font: fontConfig(), size: 18 })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 0 },
    })] });
  }
  return { headers, footers };
}

function makeDocument(spec, route, profile, tocPageMap) {
  const m = metrics(profile);
  const page = { size: { width: A4_WIDTH, height: A4_HEIGHT }, margin: MARGINS };
  const hf = headerFooter(spec, profile, m);
  const numberLists = spec.content
    .map((block, index) => ({ block, index }))
    .filter(({ block }) => block.type === "number_list")
    .map(({ index }) => ({
      reference: `soil-professional-numbers-${index}`,
      levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", start: 1, alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 630, hanging: 315 }, spacing: { line: m.bodyLine, after: m.after } } } }],
    }));

  const styles = [1, 2, 3, 4].map((level) => ({
    id: `SoilHeading${level}`,
    name: `Soil Heading ${level}`,
    basedOn: "Normal",
    next: "SoilBody",
    quickFormat: true,
    run: { font: fontConfig(FONT_HEADING, FONT_LATIN), size: m.headings[level - 1], bold: true, color: "000000" },
    paragraph: { spacing: { before: level === 1 ? 360 : 240, after: 120 }, keepNext: true, keepLines: true, outlineLevel: level - 1 },
  }));

  const bodySection = {
    properties: { page: { ...page, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } },
    headers: hf.headers,
    footers: hf.footers,
    children: contentChildren(spec, profile, m, tocPageMap),
  };
  const sections = profile.cover_mode === "none"
    ? [bodySection]
    : [
      { properties: { page }, children: titleBlock(spec, profile, m, true) },
      { ...bodySection, properties: { type: SectionType.NEXT_PAGE, page: { ...page, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } } },
    ];

  return new Document({
    creator: "soil-all-writing",
    title: spec.title,
    subject: spec.genre_profile_id,
    description: `soil-all-writing standalone ${profile.id} fallback artifact`,
    features: { updateFields: true },
    styles: {
      default: { document: { run: { font: fontConfig(), size: m.bodySize, color: "000000" }, paragraph: { spacing: { line: m.bodyLine, after: m.after } } } },
      paragraphStyles: [
        { id: "Normal", name: "Normal", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: fontConfig(), size: m.bodySize }, paragraph: { spacing: { line: m.bodyLine, after: m.after } } },
        { id: "SoilBody", name: "Soil Body", basedOn: "Normal", next: "SoilBody", quickFormat: true, run: { font: fontConfig(), size: m.bodySize }, paragraph: { spacing: { line: m.bodyLine, after: m.after }, indent: { firstLine: m.firstLine }, alignment: AlignmentType.JUSTIFIED, keepLines: true, widowControl: true } },
        ...styles,
      ],
    },
    numbering: {
      config: [
        { reference: "soil-professional-bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 630, hanging: 315 }, spacing: { line: m.bodyLine, after: m.after } } } }] },
        ...numberLists,
      ],
    },
    sections,
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const spec = JSON.parse(fs.readFileSync(args.spec, "utf8"));
  const registry = JSON.parse(fs.readFileSync(args.profiles, "utf8"));
  const tocPageMap = args.tocPageMap ? JSON.parse(fs.readFileSync(args.tocPageMap, "utf8")) : undefined;
  const { route, profile } = findRouteAndProfile(spec, registry);
  assertSpec(spec, route, profile);
  const document = makeDocument(spec, route, profile, tocPageMap);
  const buffer = await Packer.toBuffer(document);
  fs.mkdirSync(path.dirname(path.resolve(args.output)), { recursive: true });
  fs.writeFileSync(args.output, buffer);
  process.stdout.write(JSON.stringify({ status: "PASS", output: path.resolve(args.output), bytes: buffer.length, genre_profile_id: spec.genre_profile_id, format_profile_id: profile.id }) + "\n");
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error.stack || error.message}\n`);
  process.exit(1);
});
