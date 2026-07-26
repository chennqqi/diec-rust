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

bool configureMemoryMap(
    const QJsonObject &input,
    qint64 dataSize,
    XBinary::_MEMORY_MAP *memoryMap,
    QString *error
)
{
    if (!input.contains("memory_map")) {
        return true;
    }

    QJsonObject object = input.value("memory_map").toObject();
    QString fileType = object.value("file_type").toString();
    if (fileType == "binary") {
        memoryMap->fileType = XBinary::FT_BINARY;
    } else if (fileType == "pe") {
        memoryMap->fileType = XBinary::FT_PE;
    } else if (fileType == "elf") {
        memoryMap->fileType = XBinary::FT_ELF;
    } else if (fileType == "macho") {
        memoryMap->fileType = XBinary::FT_MACHO;
    } else if (fileType == "com") {
        memoryMap->fileType = XBinary::FT_COM;
    } else if (fileType == "msdos") {
        memoryMap->fileType = XBinary::FT_MSDOS;
    } else if (fileType == "amigahunk") {
        memoryMap->fileType = XBinary::FT_AMIGAHUNK;
    } else {
        *error = QString("unsupported memory_map file_type: %1").arg(fileType);
        return false;
    }

    QString endian = object.value("endian").toString();
    if (endian == "little") {
        memoryMap->endian = XBinary::ENDIAN_LITTLE;
    } else if (endian == "big") {
        memoryMap->endian = XBinary::ENDIAN_BIG;
    } else {
        *error = QString("unsupported memory_map endian: %1").arg(endian);
        return false;
    }

    memoryMap->nModuleAddress = static_cast<XADDR>(
        jsonInteger(object, "module_address", 0)
    );
    memoryMap->nCodeBase = jsonInteger(object, "code_base", 0);
    memoryMap->nStartLoadOffset =
        jsonInteger(object, "start_load_offset", 0);
    memoryMap->nBinarySize = dataSize;
    memoryMap->nImageSize = dataSize;
    memoryMap->listRecords.clear();

    QJsonArray records = object.value("records").toArray();
    if (records.isEmpty()) {
        *error = "memory_map records are empty";
        return false;
    }
    for (const QJsonValue &value : records) {
        if (!value.isObject()) {
            *error = "memory_map record is not an object";
            return false;
        }
        QJsonObject source = value.toObject();
        XBinary::_MEMORY_RECORD record = {};
        record.nOffset = jsonInteger(source, "offset", -1);
        record.nAddress = static_cast<XADDR>(
            jsonInteger(source, "address", -1)
        );
        record.nSize = jsonInteger(source, "size", 0);
        if (record.nOffset < 0 || record.nSize <= 0) {
            *error = "memory_map record has invalid offset or size";
            return false;
        }
        memoryMap->listRecords.append(record);
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
    if (!configureMemoryMap(input, data.size(), &memoryMap, error)) {
        return result;
    }
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
    result.insert("search_offset", findOffset);
    result.insert("search_size", findSize);
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
    if (input.contains("memory_map")) {
        result.insert("memory_map", input.value("memory_map"));
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
    output.insert("schema_version", 2);
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
