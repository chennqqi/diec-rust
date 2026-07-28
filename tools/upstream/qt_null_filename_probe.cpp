// Project-generated probe for the Qt5/Qt6 ISO9660 dot-entry comparison.

#include <QByteArray>
#include <QChar>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>
#include <QtGlobal>

#include <cstdio>

int main()
{
    QByteArray bytes(1, '\0');
    QString value = QString::fromLatin1(bytes);

    QJsonObject result;
    result.insert("equals_c_string", value == "\x00");
    result.insert(
        "equals_explicit_null",
        value == QString(1, QChar('\0'))
    );
    result.insert(
        "first_code_unit",
        value.isEmpty() ? -1 : value.at(0).unicode()
    );
    result.insert("qt_version", QString::fromLatin1(qVersion()));
    result.insert("string_size", value.size());

    std::printf(
        "%s\n",
        QJsonDocument(result)
            .toJson(QJsonDocument::Compact)
            .constData()
    );
    return 0;
}
