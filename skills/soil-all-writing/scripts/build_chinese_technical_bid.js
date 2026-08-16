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
    try {
      return require(candidate);
    } catch (error) {
      lastError = error;
    }
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
const MARGIN_TOP = 1417;    // 25 mm
const MARGIN_BOTTOM = 1417; // 25 mm
const MARGIN_LEFT = 1587;   // 28 mm
const MARGIN_RIGHT = 1247;  // 22 mm
const HEADER_DISTANCE = 850; // 15 mm
const FOOTER_DISTANCE = 850; // 15 mm
const CONTENT_WIDTH = A4_WIDTH - MARGIN_LEFT - MARGIN_RIGHT;
const PLATFORM_BODY_FONT = process.platform === "darwin" ? "STSong" : process.platform === "win32" ? "SimSun" : "Noto Serif CJK SC";
const PLATFORM_HEADING_FONT = process.platform === "darwin" ? "Hiragino Sans GB" : process.platform === "win32" ? "SimHei" : "Noto Sans CJK SC";
const FONT_ZH = process.env.SOIL_BODY_FONT_ZH || PLATFORM_BODY_FONT;
const FONT_HEADING = process.env.SOIL_HEADING_FONT_ZH || PLATFORM_HEADING_FONT;
const FONT_LATIN = "Times New Roman";
// CPB-1.2 default paragraph profile. User-facing rules use Chinese type-size
// names and line units. The numeric values below are only the OOXML encoding.
const BODY_SIZE = 21;              // 五号
const BODY_LINE = 360;             // 1.5 倍行距
const BODY_FIRST_LINE = 420;       // 2 个五号中文字符
const BODY_AFTER = 120;            // 段后 0.5 行
const TABLE_SIZE = 18;             // 小五号
const TABLE_LINE = 240;            // 单倍行距，自动行高

function parseArgs(argv) {
  const result = {};
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === "--spec") result.spec = argv[++i];
    else if (argv[i] === "--output") result.output = argv[++i];
    else if (argv[i] === "--toc-page-map") result.tocPageMap = argv[++i];
    else throw new Error(`Unknown argument: ${argv[i]}`);
  }
  if (!result.spec || !result.output) {
    throw new Error("Usage: build_chinese_technical_bid.js --spec spec.json --output bid.docx [--toc-page-map toc-pages.json]");
  }
  return result;
}

function assertSpec(spec) {
  if (!spec || spec.schema_version !== 1) throw new Error("spec.schema_version must be 1");
  if (!spec.cover || typeof spec.cover.project_name !== "string") throw new Error("spec.cover.project_name is required");
  if (!Array.isArray(spec.content) || spec.content.length === 0) throw new Error("spec.content must be a non-empty array");
  const allowed = new Set(["notice", "toc", "page_break", "heading", "paragraph", "bullet_list", "number_list", "table", "callout"]);
  spec.content.forEach((block, index) => {
    if (!block || !allowed.has(block.type)) throw new Error(`unsupported content block at index ${index}`);
    if (block.type === "heading" && ![1, 2, 3].includes(block.level)) throw new Error(`heading level must be 1-3 at index ${index}`);
    if (block.type === "table") {
      if (!Array.isArray(block.headers) || !Array.isArray(block.rows) || block.headers.length === 0) throw new Error(`invalid table at index ${index}`);
      for (const row of block.rows) if (!Array.isArray(row) || row.length !== block.headers.length) throw new Error(`table row width mismatch at index ${index}`);
      if (block.widths && (block.widths.length !== block.headers.length || block.widths.some((v) => Number(v) <= 0))) throw new Error(`invalid table widths at index ${index}`);
    }
  });
}

function fontConfig(zh = FONT_ZH, latin = FONT_LATIN) {
  return { ascii: latin, hAnsi: latin, eastAsia: zh, cs: latin };
}

function singleFontConfig(name) {
  return { ascii: name, hAnsi: name, eastAsia: name, cs: name };
}

function isCjkCharacter(character) {
  return /[\p{Script=Han}\u3000-\u303f\uff00-\uffef，。；：！？、（）【】《》“”‘’—…]/u.test(character);
}

function scriptSegments(value) {
  const segments = [];
  for (const character of String(value ?? "")) {
    const kind = isCjkCharacter(character) ? "cjk" : "latin";
    const previous = segments[segments.length - 1];
    if (previous && previous.kind === kind) previous.text += character;
    else segments.push({ kind, text: character });
  }
  return segments;
}

function textRuns(text, options = {}) {
  const lines = String(text ?? "").split("\n");
  const children = [];
  lines.forEach((line, index) => {
    const segments = scriptSegments(line);
    if (segments.length === 0) segments.push({ kind: "latin", text: "" });
    segments.forEach((segment, segmentIndex) => {
      const fontName = segment.kind === "cjk" ? (options.zhFont || FONT_ZH) : (options.latinFont || FONT_LATIN);
      children.push(new TextRun({
        text: segment.text,
        font: singleFontConfig(fontName),
        size: options.size || 21,
        bold: Boolean(options.bold),
        color: options.color || "000000",
        break: index > 0 && segmentIndex === 0 ? 1 : undefined,
      }));
    });
  });
  return children;
}

function bodyParagraph(text, options = {}) {
  return new Paragraph({
    children: textRuns(text, options),
    style: "SoilBody",
    alignment: options.alignment || AlignmentType.JUSTIFIED,
    spacing: { line: options.line || BODY_LINE, before: options.before || 0, after: options.after ?? BODY_AFTER },
    indent: { firstLine: options.noIndent ? 0 : BODY_FIRST_LINE },
    keepLines: true,
    widowControl: true,
  });
}

function compactParagraph(text, options = {}) {
  return new Paragraph({
    children: textRuns(text, { ...options, size: options.size || TABLE_SIZE }),
    alignment: options.alignment || AlignmentType.LEFT,
    spacing: { line: options.line || TABLE_LINE, before: options.before || 0, after: options.after ?? 0 },
    indent: { firstLine: 0, left: 0, right: 0 },
    keepLines: true,
    widowControl: true,
  });
}

function borders(color = "808080", size = 4) {
  const edge = { style: BorderStyle.SINGLE, size, color };
  return { top: edge, bottom: edge, left: edge, right: edge, insideHorizontal: edge, insideVertical: edge };
}

function cell(text, width, options = {}) {
  const paragraphs = Array.isArray(text)
    ? text.map((item) => compactParagraph(item, options))
    : [compactParagraph(String(text ?? ""), options)];
  return new TableCell({
    children: paragraphs,
    width: { size: width, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    shading: options.fill ? { type: ShadingType.CLEAR, fill: options.fill, color: "auto" } : undefined,
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
  });
}

function normalizeWidths(widths, columns) {
  const values = widths && widths.length === columns ? widths.map(Number) : Array(columns).fill(1);
  const total = values.reduce((sum, value) => sum + value, 0);
  const result = values.map((value) => Math.floor((value / total) * CONTENT_WIDTH));
  result[result.length - 1] += CONTENT_WIDTH - result.reduce((sum, value) => sum + value, 0);
  return result;
}

function dataTable(block) {
  const widths = normalizeWidths(block.widths, block.headers.length);
  const header = new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: block.headers.map((value, index) => cell(value, widths[index], {
      bold: true,
      zhFont: FONT_HEADING,
      alignment: AlignmentType.CENTER,
      size: 18,
      line: TABLE_LINE,
    })),
  });
  const rows = block.rows.map((row) => new TableRow({
    cantSplit: true,
    children: row.map((value, index) => cell(value, widths[index], {
      alignment: block.center_columns && block.center_columns.includes(index) ? AlignmentType.CENTER : AlignmentType.LEFT,
      size: 18,
      line: TABLE_LINE,
    })),
  }));
  const result = [];
  if (block.title) {
    result.push(new Paragraph({
      children: textRuns(block.title, { size: 21, bold: true, zhFont: FONT_HEADING }),
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 120 },
      keepNext: true,
    }));
  }
  result.push(new Table({
    rows: [header, ...rows],
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    borders: borders(),
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
  }));
  result.push(new Paragraph({ children: [], spacing: { after: 80 } }));
  return result;
}

function noteParagraphs(block) {
  return [new Paragraph({
    children: textRuns(block.title || "说明", { bold: true, size: 24, zhFont: FONT_HEADING }),
    spacing: { before: 240, after: 120 },
    keepNext: true,
  }), bodyParagraph(block.text || "", { size: BODY_SIZE, noIndent: true, after: BODY_AFTER })];
}

function headingEntries(spec, tocPageMap) {
  const mapped = Array.isArray(tocPageMap && tocPageMap.entries) ? tocPageMap.entries : [];
  const byKey = new Map(mapped.map((entry) => [`${entry.index}\u0000${entry.title}`, entry]));
  return spec.content
    .filter((block) => block.type === "heading")
    .map((block, index) => {
      const match = byKey.get(`${index}\u0000${block.text}`) || mapped.find((entry) => entry.title === block.text && entry.level === block.level);
      return {
        title: block.text,
        level: block.level,
        page: match && Number.isInteger(match.page) ? match.page : undefined,
      };
    });
}

function contentChildren(spec, tocPageMap) {
  const children = [];
  const tocEntries = headingEntries(spec, tocPageMap);
  let forceNextHeadingPageBreak = false;
  for (let blockIndex = 0; blockIndex < spec.content.length; blockIndex += 1) {
    const block = spec.content[blockIndex];
    if (block.type === "notice" || block.type === "callout") {
      children.push(...noteParagraphs(block));
    } else if (block.type === "toc") {
      children.push(new Paragraph({
        children: textRuns("目 录", { size: 32, bold: true, zhFont: FONT_HEADING }),
        alignment: AlignmentType.CENTER,
        spacing: { before: 160, after: 180 },
        keepNext: true,
      }));
      children.push(new TableOfContents("目 录", {
        hyperlink: false,
        headingStyleRange: "1-3",
        cachedEntries: tocEntries,
        beginDirty: true,
      }));
    } else if (block.type === "page_break") {
      // A standalone page-break paragraph after a generated TOC can be pushed
      // onto the next page when the TOC exactly fills its page, creating a
      // blank page. Attach that break to the next heading instead.
      if (blockIndex > 0 && spec.content[blockIndex - 1].type === "toc") {
        forceNextHeadingPageBreak = true;
      } else {
        children.push(new Paragraph({ children: [new PageBreak()] }));
      }
    } else if (block.type === "heading") {
      const headingBefore = block.level === 1 ? 360 : 240;
      children.push(new Paragraph({
        children: textRuns(block.text, { size: block.level === 1 ? 32 : block.level === 2 ? 28 : 24, bold: true, zhFont: FONT_HEADING }),
        style: block.level === 1 ? "SoilHeading1" : block.level === 2 ? "SoilHeading2" : "SoilHeading3",
        pageBreakBefore: Boolean(block.page_break_before || forceNextHeadingPageBreak),
        spacing: { before: headingBefore, after: 120 },
        keepNext: true,
        keepLines: true,
      }));
      forceNextHeadingPageBreak = false;
    } else if (block.type === "paragraph") {
      children.push(bodyParagraph(block.text, { noIndent: Boolean(block.no_indent), alignment: block.align === "left" ? AlignmentType.LEFT : AlignmentType.JUSTIFIED }));
    } else if (block.type === "bullet_list" || block.type === "number_list") {
      const reference = block.type === "bullet_list" ? "soil-bid-bullets" : `soil-bid-numbers-${blockIndex}`;
      for (const item of block.items || []) {
        children.push(new Paragraph({
          children: textRuns(item, { size: 21 }),
          numbering: { reference, level: 0 },
          spacing: { line: BODY_LINE, after: BODY_AFTER },
          keepLines: true,
        }));
      }
    } else if (block.type === "table") {
      children.push(...dataTable(block));
    }
  }
  return children;
}

function coverChildren(spec) {
  const cover = spec.cover;
  const spacer = (after) => new Paragraph({ children: [], spacing: { after } });
  const center = (text, size, bold = false, after = 0) => new Paragraph({
    children: textRuns(text, { size, bold, zhFont: FONT_HEADING }),
    alignment: AlignmentType.CENTER,
    spacing: { after },
    keepLines: true,
  });
  const metadata = [
    `项目编号：${cover.project_number || "【待填：项目编号】"}`,
    `投标人：${cover.bidder || "【待填：投标人全称】"}`,
    `法定代表人或授权代表：${cover.representative || "【待填：法定代表人或授权代表】"}`,
    `投标日期：${cover.date || "【待填：投标日期】"}`,
  ].map((value) => new Paragraph({
    children: textRuns(value, { size: 24 }),
    alignment: AlignmentType.CENTER,
    spacing: { after: 180 },
    keepLines: true,
  }));
  return [
    spacer(1500),
    center(cover.project_name, 44, true, 360),
    center(cover.document_type || "投标文件（技术部分）", 36, true, 1500),
    ...metadata,
  ];
}

function makeDocument(spec, tocPageMap) {
  const page = {
    size: { width: A4_WIDTH, height: A4_HEIGHT },
    margin: { top: MARGIN_TOP, bottom: MARGIN_BOTTOM, left: MARGIN_LEFT, right: MARGIN_RIGHT, header: HEADER_DISTANCE, footer: FOOTER_DISTANCE },
  };
  const headerText = spec.running_header || `${spec.cover.project_name}｜投标文件（技术部分）`;
  const header = new Header({
    children: [new Paragraph({
      children: textRuns(headerText, { size: 15, color: "595959" }),
      alignment: AlignmentType.CENTER,
      spacing: { after: 0 },
    })],
  });
  const footer = new Footer({
    children: [new Paragraph({
      children: [new TextRun({ text: "— ", font: fontConfig(), size: 18 }), new TextRun({ children: [PageNumber.CURRENT], font: fontConfig(), size: 18 }), new TextRun({ text: " —", font: fontConfig(), size: 18 })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 0 },
    })],
  });
  const numberListConfigs = spec.content
    .map((block, blockIndex) => ({ block, blockIndex }))
    .filter(({ block }) => block.type === "number_list")
    .map(({ blockIndex }) => ({
      reference: `soil-bid-numbers-${blockIndex}`,
      levels: [{
        level: 0,
        format: LevelFormat.DECIMAL,
        text: "%1.",
        start: 1,
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 630, hanging: 315 }, spacing: { line: BODY_LINE, after: BODY_AFTER } } },
      }],
    }));

  return new Document({
    creator: "soil-all-writing",
    title: spec.cover.project_name,
    subject: spec.cover.document_type || "投标文件（技术部分）",
    description: "Generated and validated in soil-all-writing standalone artifact mode",
    features: { updateFields: true },
    styles: {
      default: {
        document: {
          run: { font: fontConfig(), size: 21, color: "000000" },
          paragraph: { spacing: { line: 360, after: 80 } },
        },
      },
      paragraphStyles: [
        {
          id: "Normal", name: "Normal", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: fontConfig(), size: BODY_SIZE, color: "000000" },
          paragraph: { spacing: { line: BODY_LINE, after: BODY_AFTER }, alignment: AlignmentType.JUSTIFIED },
        },
        {
          id: "SoilBody", name: "Soil Body", basedOn: "Normal", next: "SoilBody", quickFormat: true,
          run: { font: fontConfig(), size: BODY_SIZE, color: "000000" },
          paragraph: {
            spacing: { line: BODY_LINE, before: 0, after: BODY_AFTER },
            indent: { firstLine: BODY_FIRST_LINE },
            alignment: AlignmentType.JUSTIFIED,
            keepLines: true,
            widowControl: true,
          },
        },
        {
          id: "SoilHeading1", name: "Soil Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: fontConfig(FONT_HEADING, FONT_LATIN), size: 32, bold: true, color: "000000" },
          paragraph: { spacing: { before: 360, after: 120 }, keepNext: true, keepLines: true, outlineLevel: 0 },
        },
        {
          id: "SoilHeading2", name: "Soil Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: fontConfig(FONT_HEADING, FONT_LATIN), size: 28, bold: true, color: "000000" },
          paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, keepLines: true, outlineLevel: 1 },
        },
        {
          id: "SoilHeading3", name: "Soil Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: fontConfig(FONT_HEADING, FONT_LATIN), size: 24, bold: true, color: "000000" },
          paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, keepLines: true, outlineLevel: 2 },
        },
        {
          id: "TOC1", name: "toc 1", basedOn: "Normal", next: "Normal", quickFormat: false,
          run: { font: singleFontConfig(FONT_ZH), size: 21, color: "000000" },
          paragraph: { spacing: { line: 240, after: 0 }, indent: { left: 0 } },
        },
        {
          id: "TOC2", name: "toc 2", basedOn: "Normal", next: "Normal", quickFormat: false,
          run: { font: singleFontConfig(FONT_ZH), size: 18, color: "000000" },
          paragraph: { spacing: { line: 240, after: 0 }, indent: { left: 360 } },
        },
        {
          id: "TOC3", name: "toc 3", basedOn: "Normal", next: "Normal", quickFormat: false,
          run: { font: singleFontConfig(FONT_ZH), size: 18, color: "000000" },
          paragraph: { spacing: { line: 240, after: 0 }, indent: { left: 720 } },
        },
      ],
    },
    numbering: {
      config: [
        {
          reference: "soil-bid-bullets",
          levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 630, hanging: 315 }, spacing: { line: BODY_LINE, after: BODY_AFTER } } } }],
        },
        ...numberListConfigs,
      ],
    },
    sections: [
      { properties: { page }, children: coverChildren(spec) },
      {
        properties: { type: SectionType.NEXT_PAGE, page: { ...page, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } },
        headers: { default: header },
        footers: { default: footer },
        children: contentChildren(spec, tocPageMap),
      },
    ],
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const spec = JSON.parse(fs.readFileSync(args.spec, "utf8"));
  const tocPageMap = args.tocPageMap ? JSON.parse(fs.readFileSync(args.tocPageMap, "utf8")) : undefined;
  assertSpec(spec);
  const doc = makeDocument(spec, tocPageMap);
  const buffer = await Packer.toBuffer(doc);
  fs.mkdirSync(path.dirname(path.resolve(args.output)), { recursive: true });
  fs.writeFileSync(args.output, buffer);
  process.stdout.write(JSON.stringify({ status: "PASS", output: path.resolve(args.output), bytes: buffer.length, format_profile: "CPB-1.2" }) + "\n");
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error.stack || error.message}\n`);
  process.exit(1);
});
