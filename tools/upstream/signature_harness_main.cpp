// Project-generated research harness for the pinned XBinary signature API.
// It does not modify upstream parsing or matching behavior.

#include "xbinary.h"

#include <QBuffer>
#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>

#include <cstdio>

namespace {

constexpr const char *UPSTREAM_COMMIT =
    "74eaf505c250ab47e709024e9dc41657cd8f2254";
constexpr const char *FORMATS_COMMIT =
    "1151e7254fdee3c0294ff7095edbdd7bfccf8201";

qint64 jsonInteger(
    const QJsonObject &object,
    const QString &name,
    qint64 defaultValue
)
{
    QJsonValue value = object.value(name);
    if (value.isUndefined()) {
        return defaultValue;
    }
    return static_cast<qint64>(value.toDouble());
}

bool isHexData(const QByteArray &text)
{
    if ((text.size() % 2) != 0) {
        return false;
    }
    for (char character : text) {
        bool digit = (character >= '0') && (character <= '9');
        bool lower = (character >= 'a') && (character <= 'f');
        bool upper = (character >= 'A') && (character <= 'F');
        if (!(digit || lower || upper)) {
            return false;
        }
    }
    return true;
}

QJsonObject runCase(const QJsonObject &input, QString *error)
{
    QJsonObject result;
    QString id = input.value("id").toString();
    QString pattern = input.value("pattern").toString();
    QByteArray dataHex = input.value("data_hex").toString().toLatin1();

    if (id.isEmpty()) {
        *error = "case id is empty";
        return result;
    }
    if (!isHexData(dataHex)) {
        *error = QString("invalid data_hex for %1").arg(id);
        return result;
    }

    QByteArray data = QByteArray::fromHex(dataHex);
    QBuffer buffer(&data);
    if (!buffer.open(QIODevice::ReadOnly)) {
        *error = QString("cannot open input buffer for %1").arg(id);
        return result;
    }

    XBinary binary(&buffer);
    XBinary::_MEMORY_MAP memoryMap = binary.getMemoryMap();
    qint64 offset = jsonInteger(input, "offset", 0);
    qint64 findOffset = jsonInteger(input, "find_offset", 0);
    qint64 findSize =
        jsonInteger(input, "find_size", data.size() - findOffset);

    XBinary::PDSTRUCT validState = XBinary::createPdStruct();
    bool valid = XBinary::isSignatureValid(pattern, &validState);

    XBinary::PDSTRUCT compareState = XBinary::createPdStruct();
    bool compare =
        binary.compareSignature(&memoryMap, pattern, offset, &compareState);

    qint64 findResultSize = 0;
    XBinary::PDSTRUCT findState = XBinary::createPdStruct();
    qint64 findOffsetResult = binary.find_signature(
        &memoryMap,
        findOffset,
        findSize,
        pattern,
        &findResultSize,
        &findState
    );

    QString converted = XBinary::convertSignature(pattern);
    result.insert("id", id);
    result.insert("pattern", pattern);
    result.insert("data_hex", QString::fromLatin1(data.toHex()));
    result.insert("converted", converted);
    result.insert(
        "converted_utf8_hex",
        QString::fromLatin1(converted.toUtf8().toHex())
    );
    result.insert("valid", valid);
    result.insert(
        "valid_error",
        XBinary::getPdStructErrorString(&validState)
    );
    result.insert("offset", offset);
    result.insert("compare", compare);
    result.insert(
        "compare_error",
        XBinary::getPdStructErrorString(&compareState)
    );
    result.insert("find_offset", findOffsetResult);
    result.insert("find_result_size", findResultSize);
    result.insert(
        "find_error",
        XBinary::getPdStructErrorString(&findState)
    );

    if (input.contains("base_signature")) {
        QString baseSignature = input.value("base_signature").toString();
        result.insert("base_signature", baseSignature);
        result.insert(
            "compare_strings",
            XBinary::compareSignatureStrings(baseSignature, pattern)
        );
    }

    return result;
}

}  // namespace

int main(int argc, char *argv[])
{
    QCoreApplication application(argc, argv);
    if (argc != 2) {
        std::fprintf(
            stderr,
            "usage: diec-signature-harness <vectors.json>\n"
        );
        return 2;
    }

    QFile inputFile(QString::fromLocal8Bit(argv[1]));
    if (!inputFile.open(QIODevice::ReadOnly)) {
        std::fprintf(stderr, "cannot open vector file\n");
        return 2;
    }

    QJsonParseError parseError = {};
    QJsonDocument document =
        QJsonDocument::fromJson(inputFile.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError ||
        !document.isObject()) {
        std::fprintf(stderr, "invalid vector JSON\n");
        return 2;
    }

    QJsonArray inputCases = document.object().value("cases").toArray();
    if (inputCases.isEmpty()) {
        std::fprintf(stderr, "vector list is empty\n");
        return 2;
    }

    QJsonArray outputCases;
    for (const QJsonValue &value : inputCases) {
        if (!value.isObject()) {
            std::fprintf(stderr, "vector entry is not an object\n");
            return 2;
        }
        QString error;
        QJsonObject output = runCase(value.toObject(), &error);
        if (!error.isEmpty()) {
            std::fprintf(stderr, "%s\n", error.toUtf8().constData());
            return 2;
        }
        outputCases.append(output);
    }

    QJsonObject output;
    output.insert("schema_version", 1);
    output.insert("upstream_commit", UPSTREAM_COMMIT);
    output.insert("formats_commit", FORMATS_COMMIT);
    output.insert("qt_version", qVersion());
    output.insert("case_count", outputCases.size());
    output.insert("cases", outputCases);
    std::printf(
        "%s",
        QJsonDocument(output).toJson(QJsonDocument::Indented).constData()
    );
    return 0;
}
