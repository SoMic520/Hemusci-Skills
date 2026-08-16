#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

function loadPptxGenJS() {
  const candidates = [
    "pptxgenjs",
    process.env.SOIL_SCIENCE_PPTXGEN_MODULE,
    path.join(os.homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "node_modules", "pptxgenjs"),
  ].filter(Boolean);
  let lastError;
  for (const candidate of candidates) {
    try { return require(candidate); } catch (error) { lastError = error; }
  }
  throw new Error(`Cannot load PptxGenJS. Set SOIL_SCIENCE_PPTXGEN_MODULE. ${lastError || ""}`);
}

const PptxGenJS = loadPptxGenJS();
const FONT_ZH = process.env.SOIL_VISUAL_FONT_ZH || "Noto Sans CJK SC";
const FONT_LATIN = "Times New Roman";
const BLACK = "000000";
const WHITE = "FFFFFF";
const GRAY = "737373";

function parseArgs(argv) {
  const result = {};
  for (let index = 2; index < argv.length; index += 1) {
    if (argv[index] === "--spec") result.spec = argv[++index];
    else if (argv[index] === "--profiles") result.profiles = argv[++index];
    else if (argv[index] === "--output") result.output = argv[++index];
    else throw new Error(`Unknown argument: ${argv[index]}`);
  }
  if (!result.spec || !result.profiles || !result.output) {
    throw new Error("Usage: build_chinese_scientific_visual.js --spec spec.json --profiles genre-artifact-profiles.json --output output.pptx");
  }
  return result;
}

function controls(spec, registry) {
  if (!spec || spec.schema_version !== 1) throw new Error("spec.schema_version must be 1");
  if (!["draft", "internal_review", "release"].includes(spec.lifecycle_stage)) throw new Error("spec.lifecycle_stage is invalid");
  if (typeof spec.title !== "string" || !spec.title.trim()) throw new Error("spec.title is required");
  if (!Array.isArray(spec.sections) || !spec.sections.length) throw new Error("spec.sections must be a non-empty array");
  const route = (registry.genre_routes || []).find((item) => item.id === spec.genre_profile_id);
  if (!route) throw new Error(`Unknown genre_profile_id: ${spec.genre_profile_id}`);
  const profile = (registry.format_profiles || []).find((item) => item.id === route.format_profile_id);
  if (!profile || !["pptx_poster", "pptx_slides"].includes(profile.artifact_kind)) throw new Error(`Genre ${spec.genre_profile_id} is not a PPTX visual route`);
  for (const [index, section] of spec.sections.entries()) {
    if (!section || typeof section.role !== "string" || typeof section.title !== "string") throw new Error(`section ${index} requires role and title`);
    if (!Array.isArray(section.body) || !section.body.length || !section.body.every((item) => typeof item === "string")) throw new Error(`section ${index}.body must be a non-empty string array`);
  }
  if (spec.lifecycle_stage === "release") {
    if (route.controlled_template_required_for_release) {
      if (spec.controlled_template?.state !== "received_locked" || !/^[0-9a-fA-F]{64}$/.test(spec.controlled_template?.snapshot_sha256 || "")) {
        throw new Error("Release requires a locked current event template");
      }
    }
    const roles = new Set(["title", ...spec.sections.map((section) => section.role)]);
    const missing = route.required_roles.filter((role) => !roles.has(role));
    if (missing.length) throw new Error(`Release missing required roles: ${missing.join(", ")}`);
    if (/【待填：[^】]+】/.test(JSON.stringify(spec))) throw new Error("Release cannot contain unresolved placeholders");
  }
  return { route, profile };
}

function addText(slide, text, options) {
  slide.addText(String(text ?? ""), {
    fontFace: FONT_ZH,
    color: BLACK,
    margin: 0,
    breakLine: false,
    valign: "top",
    ...options,
  });
}

function addFooter(slide, spec, width, y, index) {
  slide.addText(`${spec.document_id}  |  ${index}`, {
    x: 0.7, y, w: width - 1.4, h: 0.25,
    fontFace: FONT_LATIN, fontSize: 10, color: GRAY, margin: 0,
    align: "right", valign: "mid",
  });
}

function buildPoster(pptx, spec, profile) {
  pptx.defineLayout({ name: "SOIL_A0_PORTRAIT", width: 33.1, height: 46.8 });
  pptx.layout = "SOIL_A0_PORTRAIT";
  const slide = pptx.addSlide();
  slide.background = { color: WHITE };
  addText(slide, spec.title, { x: 1.3, y: 1.2, w: 30.5, h: 1.5, fontSize: 60, bold: true, align: "center", valign: "mid", fit: "shrink" });
  if (spec.subtitle) addText(slide, spec.subtitle, { x: 2.0, y: 2.9, w: 29.1, h: 0.7, fontSize: 28, align: "center", fit: "shrink" });
  addText(slide, `${spec.authors || ""}　${spec.organization || ""}`, { x: 2.0, y: 3.8, w: 29.1, h: 0.6, fontSize: 24, align: "center", fit: "shrink" });
  slide.addShape(pptx.ShapeType.line, { x: 1.3, y: 4.8, w: 30.5, h: 0, line: { color: BLACK, width: 1.5 } });

  const margin = 1.3;
  const gap = 0.8;
  const columnWidth = (33.1 - 2 * margin - 2 * gap) / 3;
  const rowHeight = 18.2;
  const top = 5.5;
  spec.sections.forEach((section, index) => {
    const column = index % 3;
    const row = Math.floor(index / 3);
    const x = margin + column * (columnWidth + gap);
    const y = top + row * (rowHeight + 0.8);
    addText(slide, section.title, { x, y, w: columnWidth, h: 0.8, fontSize: 30, bold: true, fit: "shrink" });
    slide.addShape(pptx.ShapeType.line, { x, y: y + 0.95, w: columnWidth, h: 0, line: { color: BLACK, width: 1 } });
    const body = section.body.map((item) => `• ${item}`).join("\n");
    addText(slide, body, { x, y: y + 1.25, w: columnWidth, h: rowHeight - 1.7, fontSize: 22, breakLine: true, fit: "shrink", paraSpaceAfterPt: 12, lineSpacingMultiple: 1.15 });
  });
  addFooter(slide, spec, 33.1, 46.1, 1);
}

function buildSlides(pptx, spec, profile) {
  pptx.layout = "LAYOUT_WIDE";
  pptx.theme = {
    headFontFace: FONT_ZH,
    bodyFontFace: FONT_ZH,
    lang: "zh-CN",
  };
  const titleSlide = pptx.addSlide();
  titleSlide.background = { color: WHITE };
  addText(titleSlide, spec.title, { x: 0.9, y: 1.7, w: 11.5, h: 1.2, fontSize: 34, bold: true, align: "center", valign: "mid", fit: "shrink" });
  if (spec.subtitle) addText(titleSlide, spec.subtitle, { x: 1.2, y: 3.0, w: 10.9, h: 0.6, fontSize: 20, align: "center", fit: "shrink" });
  addText(titleSlide, `${spec.authors || ""}\n${spec.organization || ""}`, { x: 2.0, y: 4.2, w: 9.3, h: 0.9, fontSize: 18, align: "center", breakLine: true, fit: "shrink" });
  addFooter(titleSlide, spec, 13.333, 7.1, 1);

  spec.sections.forEach((section, index) => {
    const slide = pptx.addSlide();
    slide.background = { color: WHITE };
    addText(slide, section.title, { x: 0.7, y: 0.45, w: 11.9, h: 0.65, fontSize: 28, bold: true, fit: "shrink" });
    slide.addShape(pptx.ShapeType.line, { x: 0.7, y: 1.2, w: 11.9, h: 0, line: { color: BLACK, width: 1 } });
    addText(slide, section.body.map((item) => `• ${item}`).join("\n"), {
      x: 1.0, y: 1.55, w: 11.3, h: 4.8, fontSize: 20, breakLine: true,
      fit: "shrink", paraSpaceAfterPt: 12, lineSpacingMultiple: 1.15,
    });
    if (section.source) addText(slide, `来源：${section.source}`, { x: 1.0, y: 6.45, w: 11.3, h: 0.3, fontSize: 11, color: GRAY, fit: "shrink" });
    addFooter(slide, spec, 13.333, 7.1, index + 2);
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const spec = JSON.parse(fs.readFileSync(args.spec, "utf8"));
  const registry = JSON.parse(fs.readFileSync(args.profiles, "utf8"));
  const { profile } = controls(spec, registry);
  const pptx = new PptxGenJS();
  pptx.author = "soil-all-writing";
  pptx.company = "soil-all-writing";
  pptx.subject = `${spec.genre_profile_id}|${profile.id}`;
  pptx.title = spec.title;
  pptx.lang = "zh-CN";
  pptx.theme = { headFontFace: FONT_ZH, bodyFontFace: FONT_ZH, lang: "zh-CN" };
  if (profile.artifact_kind === "pptx_poster") buildPoster(pptx, spec, profile);
  else buildSlides(pptx, spec, profile);
  fs.mkdirSync(path.dirname(path.resolve(args.output)), { recursive: true });
  await pptx.writeFile({ fileName: path.resolve(args.output) });
  const bytes = fs.statSync(path.resolve(args.output)).size;
  process.stdout.write(JSON.stringify({ status: "PASS", output: path.resolve(args.output), bytes, genre_profile_id: spec.genre_profile_id, format_profile_id: profile.id }) + "\n");
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error.stack || error.message}\n`);
  process.exit(1);
});
