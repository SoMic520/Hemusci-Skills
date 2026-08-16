import AppKit
import Foundation
import Vision

struct Observation: Codable {
    let text: String
    let confidence: Float
    let box: [Double]
    let alternatives: [String]
}

struct Payload: Codable {
    let schema: String
    let engine: String
    let image: String
    let observations: [Observation]
}

func recognize(_ source: URL) throws -> Payload {
    guard let image = NSImage(contentsOf: source),
          let data = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: data),
          let cgImage = bitmap.cgImage else {
        throw NSError(domain: "soil-methods-consultant", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "Cannot load image: \(source.path)"])
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.usesLanguageCorrection = true
    request.minimumTextHeight = 0.004
    try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])

    let rows: [Observation] = (request.results ?? []).compactMap { result in
        let candidates = result.topCandidates(3)
        guard let top = candidates.first else { return nil }
        let rect = result.boundingBox
        return Observation(
            text: top.string,
            confidence: top.confidence,
            box: [rect.origin.x, rect.origin.y, rect.size.width, rect.size.height],
            alternatives: candidates.dropFirst().map { $0.string }
        )
    }
    return Payload(
        schema: "book-digitization.ocr-page.v1",
        engine: "Apple Vision VNRecognizeTextRequest accurate",
        image: source.path,
        observations: rows
    )
}

let arguments = CommandLine.arguments.dropFirst()
guard arguments.count == 2 else {
    fputs("usage: apple_vision_ocr IMAGE OUTPUT_JSON\n", stderr)
    exit(2)
}

let input = URL(fileURLWithPath: String(arguments[arguments.startIndex]))
let output = URL(fileURLWithPath: String(arguments[arguments.index(after: arguments.startIndex)]))
do {
    let payload = try recognize(input)
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
    let data = try encoder.encode(payload)
    try FileManager.default.createDirectory(
        at: output.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    try data.write(to: output, options: .atomic)
} catch {
    fputs("\(error)\n", stderr)
    exit(1)
}
