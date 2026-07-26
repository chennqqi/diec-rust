// Project-generated research harness for pinned Qt QObject HostApi behavior.
// It links unmodified upstream Binary_Script and PE_Script implementations.

#include "binary_script.h"
#include "pe_script.h"
#include "xbinary.h"
#include "xpe.h"

#include <QBuffer>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#ifdef QT_SCRIPT_LIB
#include <QScriptEngine>
#include <QScriptValue>
#else
#include <QJSEngine>
#include <QJSValue>
#endif
#include <QString>

#include <cstdio>

namespace {

#ifdef QT_SCRIPT_LIB
using ScriptEngine = QScriptEngine;
using ScriptValue = QScriptValue;
#else
using ScriptEngine = QJSEngine;
using ScriptValue = QJSValue;
#endif

constexpr const char *UPSTREAM_COMMIT =
    "74eaf505c250ab47e709024e9dc41657cd8f2254";
constexpr const char *XSCANENGINE_COMMIT =
    "dfe4a419e4f491bb23688ba03c5a5bf39e34da83";
constexpr const char *RULES_COMMIT =
    "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";
constexpr const char *PE_INIT_PATH =
    "/opt/die-source/Detect-It-Easy/db/PE/_init";
constexpr const char *PE_INIT_SHA256 =
    "26f5912c5ac137ed44d0d9edade8d3ce65501a61ce06d0491db5e1faa59c1f90";

QString normalizeObjectAddress(const QString &text)
{
    QString result = text;
    result.replace(
        QRegularExpression(
            "([A-Za-z_][A-Za-z0-9_:]*)\\(0x[0-9a-fA-F]+\\)"
        ),
        "\\1(<address>)"
    );
    return result;
}

QJsonObject evaluate(
    ScriptEngine *engine,
    const QString &source,
    const QString &fileName
)
{
#ifdef QT_SCRIPT_LIB
    engine->clearExceptions();
#endif
    ScriptValue value = engine->evaluate(source, fileName);

    QJsonObject output;
    output.insert("source", source);
    output.insert("is_error", value.isError());
    output.insert("is_undefined", value.isUndefined());
    output.insert("is_null", value.isNull());
    output.insert("is_boolean", value.isBool());
    output.insert("is_number", value.isNumber());
    output.insert("is_string", value.isString());
    if (value.isBool()) {
        output.insert("boolean", value.toBool());
    }
    if (value.isNumber()) {
        output.insert("number", value.toNumber());
    }
    if (value.isString() || value.isError()) {
        output.insert(
            "string",
            normalizeObjectAddress(value.toString())
        );
    }
    if (value.isError()) {
        output.insert("error_name", value.property("name").toString());
        output.insert(
            "error_message",
            normalizeObjectAddress(
                value.property("message").toString()
            )
        );
        output.insert(
            "error_line",
#ifdef QT_SCRIPT_LIB
            value.property("lineNumber").toInt32()
#else
            value.property("lineNumber").toInt()
#endif
        );
        QJsonArray backtrace;
#ifdef QT_SCRIPT_LIB
        for (const QString &line : engine->uncaughtExceptionBacktrace()) {
            backtrace.append(line);
        }
#else
        for (
            const QString &line :
            value.property("stack").toString().split('\n')
        ) {
            if (!line.isEmpty()) {
                backtrace.append(line);
            }
        }
#endif
        output.insert("backtrace", backtrace);
    }
    return output;
}

QJsonObject binaryObservations()
{
    QByteArray bytes("ABC\0", 4);
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::ReadOnly);
    XBinary binary(&buffer);
    Binary_Script::OPTIONS options = {};
    XBinary::PDSTRUCT state = XBinary::createPdStruct();
    Binary_Script script(
        &binary,
        XBinary::FILEPART_HEADER,
        options,
        &state
    );
    ScriptEngine engine;
#ifndef QT_SCRIPT_LIB
    QJSEngine::setObjectOwnership(&script, QJSEngine::CppOwnership);
#endif
    engine.globalObject().setProperty("X", engine.newQObject(&script));

    QJsonObject output;
    output.insert(
        "u8_function_length",
        evaluate(&engine, "X.U8.length", "u8-function-length.js")
    );
    output.insert(
        "u8_exact",
        evaluate(&engine, "X.U8(0)", "u8-exact.js")
    );
    output.insert(
        "u8_missing",
        evaluate(&engine, "X.U8()", "u8-missing.js")
    );
    output.insert(
        "u8_extra",
        evaluate(&engine, "X.U8(0, 12)", "u8-extra.js")
    );
    output.insert(
        "u8_string",
        evaluate(&engine, "X.U8('0')", "u8-string.js")
    );
    output.insert(
        "u8_null",
        evaluate(&engine, "X.U8(null)", "u8-null.js")
    );
    output.insert(
        "u8_undefined",
        evaluate(&engine, "X.U8(undefined)", "u8-undefined.js")
    );
    output.insert(
        "u8_boolean",
        evaluate(&engine, "X.U8(false)", "u8-boolean.js")
    );
    output.insert(
        "sa_function_length",
        evaluate(&engine, "X.SA.length", "sa-function-length.js")
    );
    output.insert(
        "sa_exact",
        evaluate(&engine, "X.SA(0, 1)", "sa-exact.js")
    );
    output.insert(
        "sa_missing",
        evaluate(&engine, "X.SA(0)", "sa-missing.js")
    );
    output.insert(
        "sa_extra",
        evaluate(&engine, "X.SA(0, 1, 99)", "sa-extra.js")
    );
    output.insert(
        "sc_function_length",
        evaluate(&engine, "X.SC.length", "sc-function-length.js")
    );
    output.insert(
        "sc_exact",
        evaluate(
            &engine,
            "X.SC(0, 1, 'System')",
            "sc-exact.js"
        )
    );
    output.insert(
        "sc_default_one",
        evaluate(&engine, "X.SC(0)", "sc-default-one.js")
    );
    output.insert(
        "sc_default_two",
        evaluate(&engine, "X.SC(0, 1)", "sc-default-two.js")
    );
    output.insert(
        "sc_missing",
        evaluate(&engine, "X.SC()", "sc-missing.js")
    );
    output.insert(
        "sc_null_encoding",
        evaluate(
            &engine,
            "X.SC(0, 1, null)",
            "sc-null-encoding.js"
        )
    );
    output.insert(
        "sc_number_encoding",
        evaluate(
            &engine,
            "X.SC(0, 1, 42)",
            "sc-number-encoding.js"
        )
    );
    output.insert(
        "sc_extra",
        evaluate(
            &engine,
            "X.SC(0, 1, 'System', 99)",
            "sc-extra.js"
        )
    );
    return output;
}

QJsonObject peObservations(QString *error)
{
    QByteArray bytes(4096, '\0');
    bytes[0] = 'M';
    bytes[1] = 'Z';
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::ReadOnly);
    XPE pe(&buffer);
    Binary_Script::OPTIONS options = {};
    XBinary::PDSTRUCT state = XBinary::createPdStruct();
    PE_Script script(
        &pe,
        XBinary::FILEPART_HEADER,
        options,
        &state
    );
    ScriptEngine engine;
#ifndef QT_SCRIPT_LIB
    QJSEngine::setObjectOwnership(&script, QJSEngine::CppOwnership);
#endif
    engine.globalObject().setProperty("PE", engine.newQObject(&script));

    QFile initFile(QString::fromLatin1(PE_INIT_PATH));
    if (!initFile.open(QIODevice::ReadOnly)) {
        *error = "cannot open fixed PE/_init";
        return {};
    }
    QByteArray initBytes = initFile.readAll();
    QByteArray initHash =
        QCryptographicHash::hash(
            initBytes,
            QCryptographicHash::Sha256
        ).toHex();
    if (initHash != QByteArray(PE_INIT_SHA256)) {
        *error = "fixed PE/_init hash mismatch";
        return {};
    }

    QJsonObject output;
    output.insert("parser_valid", pe.isValid());
    output.insert(
        "get_ep_signature_type_before_init",
        evaluate(
            &engine,
            "typeof PE.getEPSignature",
            "get-ep-signature-type-before-init.js"
        )
    );
    output.insert(
        "get_entry_point_signature_type_before_init",
        evaluate(
            &engine,
            "typeof PE.getEntryPointSignature",
            "get-entry-point-signature-type-before-init.js"
        )
    );
    QJsonObject initEvaluation = evaluate(
        &engine,
        QString::fromUtf8(initBytes),
        QString::fromLatin1(PE_INIT_PATH)
    );
    output.insert("init_evaluation", initEvaluation);
    if (initEvaluation.value("is_error").toBool()) {
        *error = "fixed PE/_init evaluation failed";
        return output;
    }
    output.insert(
        "get_ep_signature_type_after_init",
        evaluate(
            &engine,
            "typeof PE.getEPSignature",
            "get-ep-signature-type-after-init.js"
        )
    );
    output.insert(
        "get_entry_point_signature_type_after_init",
        evaluate(
            &engine,
            "typeof PE.getEntryPointSignature",
            "get-entry-point-signature-type-after-init.js"
        )
    );
    output.insert(
        "get_ep_signature_call",
        evaluate(
            &engine,
            "PE.getEPSignature(19, 14)",
            "get-ep-signature-call.js"
        )
    );
    return output;
}

}  // namespace

int main(int argc, char *argv[])
{
    QCoreApplication application(argc, argv);
    if (argc != 1) {
        std::fprintf(stderr, "host arity harness takes no arguments\n");
        return 2;
    }

    QString error;
    QJsonObject output;
    output.insert("schema_version", 1);
    output.insert("upstream_commit", UPSTREAM_COMMIT);
    output.insert("xscanengine_commit", XSCANENGINE_COMMIT);
    output.insert("rules_commit", RULES_COMMIT);
    output.insert("qt_version", QT_VERSION_STR);
    output.insert(
        "pe_init",
        QJsonObject{
            {"path", PE_INIT_PATH},
            {"sha256", PE_INIT_SHA256},
        }
    );
    output.insert("binary", binaryObservations());
    output.insert("pe", peObservations(&error));
    if (!error.isEmpty()) {
        std::fprintf(stderr, "%s\n", error.toUtf8().constData());
        return 2;
    }

    QByteArray serialized =
        QJsonDocument(output).toJson(QJsonDocument::Compact);
    std::fwrite(
        serialized.constData(),
        1,
        static_cast<size_t>(serialized.size()),
        stdout
    );
    std::fputc('\n', stdout);
    return 0;
}
