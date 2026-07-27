// Project-generated research harness for the branch-only BW DOS16M path.
// It links the unmodified pinned engine and changes only a QIODevice property.

#include "die_script.h"
#include "xformats.h"

#include <QBuffer>
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

#include <cstdio>

namespace {

constexpr const char *UPSTREAM_COMMIT =
    "74eaf505c250ab47e709024e9dc41657cd8f2254";
constexpr const char *FORMATS_COMMIT =
    "1151e7254fdee3c0294ff7095edbdd7bfccf8201";
constexpr const char *XSCANENGINE_COMMIT =
    "dfe4a419e4f491bb23688ba03c5a5bf39e34da83";
constexpr const char *INPUT_HEX = "42570000000000000000";

QJsonArray serializeRecords(
    const QList<XScanEngine::SCANSTRUCT> &records
)
{
    QJsonArray output;
    for (const XScanEngine::SCANSTRUCT &record : records) {
        QJsonObject item;
        item.insert(
            "filetype",
            XBinary::fileTypeIdToString(record.id.fileType)
        );
        item.insert("type", record.sType);
        item.insert("name", record.sName);
        item.insert("unknown", record.bIsUnknown);
        output.append(item);
    }
    return output;
}

QJsonObject runCase(bool forceFiletypes)
{
    QByteArray input = QByteArray::fromHex(INPUT_HEX);
    QBuffer buffer(&input);
    buffer.setProperty("FileName", "probe.bin");
    // scanProcess otherwise copies small devices into a fresh QBuffer and
    // intentionally does not propagate arbitrary source properties.
    buffer.setProperty(
        "Memory",
        reinterpret_cast<quint64>(input.constData())
    );
    if (forceFiletypes) {
        buffer.setProperty("filetypes", "BWDOS16M");
    }
    if (!buffer.open(QIODevice::ReadOnly)) {
        return {{"error", "cannot open input buffer"}};
    }

    XBinary::PDSTRUCT detectorState = XBinary::createPdStruct();
    const QSet<XBinary::FT> detected = XFormats::getFileTypes(
        &buffer,
        true,
        &detectorState
    );
    buffer.seek(0);

    XScanEngine::SCAN_OPTIONS options = {};
    options.bShowType = true;
    options.bShowInfo = true;
    options.bShowVersion = true;
    XBinary::PDSTRUCT scanState = XBinary::createPdStruct();
    DiE_Script engine;
    const XScanEngine::SCAN_RESULT result = engine.scanDevice(
        &buffer,
        &options,
        &scanState
    );

    QJsonObject output;
    output.insert(
        "id",
        forceFiletypes ? "forced_property" : "automatic_detection"
    );
    output.insert("forced", forceFiletypes);
    output.insert(
        "property",
        buffer.property("filetypes").toString()
    );
    output.insert(
        "detected_filetypes",
        XBinary::fileTypesToString(detected)
    );
    output.insert(
        "initial_filetype",
        XBinary::fileTypeIdToString(result.ftInit)
    );
    output.insert("records", serializeRecords(result.listRecords));
    output.insert("error_count", result.listErrors.size());
    output.insert(
        "scan_success",
        XBinary::isPdStructSuccess(&scanState)
    );
    return output;
}

}  // namespace

int main(int argc, char *argv[])
{
    QCoreApplication application(argc, argv);
    Q_UNUSED(application)

    QJsonArray cases;
    cases.append(runCase(false));
    cases.append(runCase(true));

    QJsonObject output;
    output.insert("schema_version", 1);
    output.insert("upstream_commit", UPSTREAM_COMMIT);
    output.insert("formats_commit", FORMATS_COMMIT);
    output.insert("xscanengine_commit", XSCANENGINE_COMMIT);
    output.insert("input_hex", INPUT_HEX);
    output.insert("case_count", cases.size());
    output.insert("cases", cases);
    std::printf(
        "%s",
        QJsonDocument(output).toJson(QJsonDocument::Indented).constData()
    );
    return 0;
}
