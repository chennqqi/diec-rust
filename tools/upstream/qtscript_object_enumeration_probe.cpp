#include <QCoreApplication>
#include <QScriptEngine>
#include <QTextStream>

int main(int argc, char **argv) {
    QCoreApplication application(argc, argv);
    QScriptEngine engine;
    const QScriptValue result = engine.evaluate(R"JS(
(function () {
    var inherited = [];
    for (var inheritedKey in Object.prototype) {
        inherited.push(inheritedKey);
    }
    var refs = {
        "'$'11'@P:Microsoft.VisualBasic'00": "VB.NET",
        "%%%%%%%%%%'.cs'00": "C#",
        "'$'11'@P:FSharp.Core'00": "F#",
        "'std::'%%%%%%": "C++"
    };
    var keys = [];
    for (var key in refs) {
        keys.push(key);
    }
    return JSON.stringify({
        inherited_enumerable_keys: inherited,
        refs_for_in_keys: keys
    });
}())
)JS");
    if (result.isError()) {
        QTextStream(stderr) << result.toString() << '\n';
        return 1;
    }
    QTextStream(stdout) << result.toString() << '\n';
    return 0;
}
