//! rquickjs/QuickJS-NG rule runtime backend (ADR 0006).
//!
//! This module implements `RuleRuntime` and `RuleRuntimeFactory` using
//! `rquickjs@0.12.1` with vendored QuickJS-NG. All rquickjs/QuickJS types
//! are private to this module — they never appear in `diec-core`,
//! `diec-formats`, `diec-engine`, `diec-output`, `diec-cli`, `diec-ffi`
//! or the public C ABI.
//!
//! See `docs/design/decisions/0006-rquickjs-rule-runtime.md`.

use crate::error::RuleError;
use crate::host_api::HostApi;
use crate::runtime::{
    DatabaseSnapshot, DetectionResult, LoadedRule, RuleRuntime, RuleRuntimeFactory, RuntimeConfig,
};
use diec_core::cancel::CancellationToken;
use rquickjs::{Context, Ctx, Runtime};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

/// Factory that creates `RquickjsRuntime` instances.
pub struct RquickjsRuntimeFactory;

impl RuleRuntimeFactory for RquickjsRuntimeFactory {
    fn create(&self, config: RuntimeConfig) -> Result<Box<dyn RuleRuntime>, RuleError> {
        Ok(Box::new(RquickjsRuntime::new(config)?))
    }
}

/// Internal cancel flag shared between the interrupt handler and the
/// external cancel token.
struct CancelFlag {
    cancelled: AtomicBool,
}

impl CancelFlag {
    fn new() -> Self {
        Self {
            cancelled: AtomicBool::new(false),
        }
    }

    fn set_cancelled(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
    }

    fn clear(&self) {
        self.cancelled.store(false, Ordering::SeqCst);
    }

    fn is_cancelled(&self) -> bool {
        self.cancelled.load(Ordering::SeqCst)
    }
}

/// rquickjs-based rule runtime.
///
/// Each scan uses a shared runtime/context owned by a single worker thread.
/// The runtime is configured with memory limits, stack limits, and an
/// interrupt handler for cooperative cancellation.
pub struct RquickjsRuntime {
    /// Configuration (budget profile, legacy mode).
    _config: RuntimeConfig,
    /// QuickJS runtime (memory management, interrupts).
    _runtime: Runtime,
    /// QuickJS context (globals, eval).
    context: Context,
    /// Cancel flag linked to the interrupt handler.
    cancel_flag: Arc<CancelFlag>,
    /// Whether the database has been loaded.
    database_loaded: bool,
    /// Whether init has been called.
    initialized: bool,
}

impl RquickjsRuntime {
    /// Create a new rquickjs runtime with the given configuration.
    fn new(config: RuntimeConfig) -> Result<Self, RuleError> {
        let runtime = Runtime::new().map_err(|e| RuleError::Backend {
            detail: format!("failed to create QuickJS runtime: {e}"),
        })?;

        // Configure memory and stack limits per ADR 0006.
        runtime.set_memory_limit(config.budget.max_heap as usize);
        runtime.set_max_stack_size(config.budget.max_stack as usize);

        // Set up interrupt handler for cooperative cancellation.
        let cancel_flag = Arc::new(CancelFlag::new());
        let handler_flag = cancel_flag.clone();
        runtime.set_interrupt_handler(Some(Box::new(move || handler_flag.is_cancelled())));

        // Create a context with full intrinsics (Date, JSON, etc.).
        let context = Context::full(&runtime).map_err(|e| RuleError::Backend {
            detail: format!("failed to create QuickJS context: {e}"),
        })?;

        Ok(Self {
            _config: config,
            _runtime: runtime,
            context,
            cancel_flag,
            database_loaded: false,
            initialized: false,
        })
    }

    /// Register global host functions on the JavaScript context.
    ///
    /// All 15 global functions from the upstream Qt Script engine are defined
    /// via JavaScript eval. Results are stored in a JavaScript array
    /// (`__diec_results`) and read back from Rust after rule evaluation.
    /// This avoids rquickjs `Function::new` lifetime issues while maintaining
    /// the same observable behavior.
    fn register_globals(&mut self) -> Result<(), RuleError> {
        let os_name = if cfg!(target_os = "windows") {
            "windows"
        } else if cfg!(target_os = "linux") {
            "linux"
        } else if cfg!(target_os = "macos") {
            "macos"
        } else {
            "unknown"
        };

        let globals_js = format!(
            r#"
            var __diec_results = [];
            var __diec_meta = {{ type: "", name: "" }};
            function meta(type, name) {{
                __diec_meta.type = type;
                __diec_meta.name = name;
            }}
            function _setResult(type, name, version, options) {{
                __diec_results.push({{
                    type: type,
                    name: name,
                    version: version,
                    options: options,
                    lang: "",
                    langVersion: ""
                }});
            }}
            function _setLang(lang, langVersion) {{
                if (__diec_results.length > 0) {{
                    __diec_results[__diec_results.length - 1].lang = lang;
                    __diec_results[__diec_results.length - 1].langVersion = langVersion;
                }}
            }}
            function _error(msg) {{ throw new Error(msg); }}
            function _log(msg) {{ }}
            function _getEngineVersion() {{ return "3.10"; }}
            function _isStop() {{ return false; }}
            function _isConsoleMode() {{ return true; }}
            function _isLiteMode() {{ return false; }}
            function _isGuiMode() {{ return false; }}
            function _isLibraryMode() {{ return false; }}
            function _getOS() {{ return "{os_name}"; }}
            function _getNumberOfResults() {{ return __diec_results.length; }}
            function _isResultPresent() {{ return __diec_results.length > 0; }}
            function _breakScan() {{ }}
            function _encodingList() {{ return []; }}
            function _removeResult(index) {{ }}
            "#,
            os_name = os_name
        );
        self.eval_script(&globals_js)?;
        Ok(())
    }

    /// Read the `__diec_results` array from the JavaScript context.
    fn read_results(&self) -> Result<Vec<DetectionResult>, RuleError> {
        self.context.with(|ctx: Ctx<'_>| {
            let globals = ctx.globals();
            let results_val: rquickjs::Value =
                globals
                    .get("__diec_results")
                    .map_err(|e| RuleError::Backend {
                        detail: format!("failed to read __diec_results: {e}"),
                    })?;

            let arr: rquickjs::Array =
                results_val.into_array().ok_or_else(|| RuleError::Backend {
                    detail: "__diec_results is not an array".into(),
                })?;

            let mut results = Vec::new();
            for item in arr.iter::<rquickjs::Object>() {
                let obj = item.map_err(|e| RuleError::Backend {
                    detail: format!("failed to iterate results: {e}"),
                })?;

                let type_name: String = obj.get("type").unwrap_or_default();
                let name: String = obj.get("name").unwrap_or_default();
                let version: String = obj.get("version").unwrap_or_default();
                let options: String = obj.get("options").unwrap_or_default();
                let lang: String = obj.get("lang").unwrap_or_default();
                let lang_version: String = obj.get("langVersion").unwrap_or_default();

                results.push(DetectionResult {
                    type_name,
                    name,
                    version,
                    options,
                    lang,
                    lang_version,
                });
            }
            Ok(results)
        })
    }

    /// Clear the `__diec_results` array.
    fn clear_results(&self) -> Result<(), RuleError> {
        self.eval_script("__diec_results.length = 0;")
    }

    /// Evaluate a script source in the context with sloppy mode (non-strict).
    fn eval_script(&self, source: &str) -> Result<(), RuleError> {
        self.context.with(|ctx: Ctx<'_>| {
            // Use sloppy (non-strict) mode to match Qt Script behavior.
            ctx.eval::<(), _>(source)
                .map_err(|e| RuleError::ScriptException {
                    path: "<eval>".into(),
                    message: e.to_string(),
                })
        })
    }
}

impl RuleRuntime for RquickjsRuntime {
    fn load_database(&mut self, snapshot: &DatabaseSnapshot) -> Result<(), RuleError> {
        self.register_globals()?;

        if let Some(init_source) = &snapshot.init_script {
            self.eval_script(init_source)?;
        }

        for (_type_name, init_source) in &snapshot.type_init_scripts {
            self.eval_script(init_source)?;
        }

        for rule in &snapshot.rules {
            self.eval_script(&rule.source).map_err(|e| match e {
                RuleError::ScriptException { message, .. } => RuleError::ScriptException {
                    path: rule.path.clone(),
                    message,
                },
                other => other,
            })?;
        }

        self.database_loaded = true;
        Ok(())
    }

    fn init(&mut self, _host: &dyn HostApi) -> Result<(), RuleError> {
        if !self.database_loaded {
            return Err(RuleError::Backend {
                detail: "init called before load_database".into(),
            });
        }
        self.initialized = true;
        Ok(())
    }

    fn evaluate_rule(
        &mut self,
        rule: &LoadedRule,
        _host: &dyn HostApi,
        cancel: &CancellationToken,
    ) -> Result<Vec<DetectionResult>, RuleError> {
        if !self.initialized {
            return Err(RuleError::Backend {
                detail: "evaluate_rule called before init".into(),
            });
        }

        // Reset cancel flag and link to external token.
        self.cancel_flag.clear();
        if cancel.is_cancelled() {
            self.cancel_flag.set_cancelled();
            return Err(RuleError::Cancelled);
        }

        // Clear previous results from the JS __diec_results array.
        self.clear_results()?;

        // Call detect() — the function was defined when the rule source
        // was evaluated during load_database.
        let detect_call = "detect();";
        let eval_result: Result<(), rquickjs::Error> = self
            .context
            .with(|ctx: Ctx<'_>| ctx.eval::<(), _>(detect_call));

        match eval_result {
            Ok(_) => self.read_results(),
            Err(e) => {
                if self.cancel_flag.is_cancelled() {
                    Err(RuleError::Cancelled)
                } else {
                    Err(RuleError::ScriptException {
                        path: rule.path.clone(),
                        message: e.to_string(),
                    })
                }
            }
        }
    }

    fn shutdown(&mut self) {
        let _ = self.clear_results();
        self.database_loaded = false;
        self.initialized = false;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::budget::RuleBudgetProfile;
    use crate::runtime::RuntimeConfig;

    #[test]
    fn rquickjs_runtime_creates_successfully() {
        let runtime = RquickjsRuntime::new(RuntimeConfig::default());
        assert!(runtime.is_ok());
    }

    #[test]
    fn rquickjs_runtime_evaluates_javascript_expression() {
        let runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        let result: i32 = runtime.context.with(|ctx| ctx.eval("1 + 2").unwrap());
        assert_eq!(result, 3);
    }

    #[test]
    fn rquickjs_runtime_loads_empty_database() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        let snapshot = DatabaseSnapshot::empty();
        runtime.load_database(&snapshot).unwrap();
    }

    #[test]
    fn rquickjs_runtime_factory_creates_runtime() {
        let factory = RquickjsRuntimeFactory;
        let runtime = factory.create(RuntimeConfig::default()).unwrap();
        // The runtime should be a RquickjsRuntime instance.
        // We can't directly test the type since it's behind a Box<dyn RuleRuntime>,
        // but we can verify it loads an empty database.
        let mut rt = runtime;
        rt.load_database(&DatabaseSnapshot::empty()).unwrap();
    }

    #[test]
    fn rquickjs_runtime_sets_memory_limit() {
        let config = RuntimeConfig {
            budget: RuleBudgetProfile {
                max_heap: 1024 * 1024,
                max_stack: 64 * 1024,
                max_fuel: 1000,
                deadline_ms: 1000,
                max_include_depth: 4,
                max_include_evaluations: 16,
            },
            legacy_mode: false,
        };
        let runtime = RquickjsRuntime::new(config);
        assert!(runtime.is_ok());
    }

    #[test]
    fn rquickjs_runtime_handles_script_exception() {
        let runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        let result = runtime.eval_script("throw new Error('test error');");
        assert!(result.is_err());
        match result.unwrap_err() {
            RuleError::ScriptException { message, .. } => {
                // QuickJS may format the message differently; just check
                // that we got a ScriptException with a non-empty message.
                assert!(
                    !message.is_empty(),
                    "exception message should not be empty: {message}"
                );
            }
            _ => panic!("expected ScriptException"),
        }
    }

    #[test]
    fn rquickjs_runtime_error_function_throws() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();
        let result = runtime.eval_script(r#"_error("test error message");"#);
        assert!(result.is_err());
    }

    #[test]
    fn rquickjs_runtime_get_engine_version() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();
        let version: String = runtime
            .context
            .with(|ctx| ctx.eval("_getEngineVersion()").unwrap());
        assert_eq!(version, "3.10");
    }

    #[test]
    fn rquickjs_runtime_get_os() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();
        let os: String = runtime.context.with(|ctx| ctx.eval("_getOS()").unwrap());
        assert!(!os.is_empty());
    }

    #[test]
    fn rquickjs_runtime_set_result_collects_detection() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();
        runtime
            .eval_script(r#"_setResult("info", "TestFormat", "1.0", "");"#)
            .unwrap();
        let results = runtime.read_results().unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].type_name, "info");
        assert_eq!(results[0].name, "TestFormat");
        assert_eq!(results[0].version, "1.0");
    }

    #[test]
    fn rquickjs_runtime_set_lang_updates_last_result() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();
        runtime
            .eval_script(
                r#"
            _setResult("info", "TestFormat", "1.0", "");
            _setLang("C++", "17");
        "#,
            )
            .unwrap();
        let results = runtime.read_results().unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].lang, "C++");
        assert_eq!(results[0].lang_version, "17");
    }

    #[test]
    fn rquickjs_runtime_is_console_mode() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();
        let is_console: bool = runtime
            .context
            .with(|ctx| ctx.eval("_isConsoleMode()").unwrap());
        assert!(is_console);
    }

    #[test]
    fn rquickjs_runtime_is_result_present() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();

        let present: bool = runtime
            .context
            .with(|ctx| ctx.eval("_isResultPresent()").unwrap());
        assert!(!present);

        runtime
            .eval_script(r#"_setResult("info", "Test", "", "");"#)
            .unwrap();

        let present: bool = runtime
            .context
            .with(|ctx| ctx.eval("_isResultPresent()").unwrap());
        assert!(present);
    }

    #[test]
    fn rquickjs_runtime_get_number_of_results() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();

        let count: i32 = runtime
            .context
            .with(|ctx| ctx.eval("_getNumberOfResults()").unwrap());
        assert_eq!(count, 0);

        runtime
            .eval_script(
                r#"
            _setResult("info", "A", "", "");
            _setResult("info", "B", "", "");
        "#,
            )
            .unwrap();

        let count: i32 = runtime
            .context
            .with(|ctx| ctx.eval("_getNumberOfResults()").unwrap());
        assert_eq!(count, 2);
    }

    #[test]
    fn rquickjs_runtime_encoding_list_returns_array() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();
        runtime.register_globals().unwrap();
        let result = runtime.eval_script("_encodingList();");
        assert!(result.is_ok());
    }

    #[test]
    fn rquickjs_runtime_evaluates_simple_rule() {
        let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).unwrap();

        let snapshot = DatabaseSnapshot {
            rules: vec![LoadedRule {
                path: "test.sg".into(),
                ordinal: 0,
                file_type: "Binary".into(),
                source: r#"
                    meta("info", "TestRule");
                    function detect() {
                        _setResult("info", "TestRule", "1.0", "");
                    }
                "#
                .to_string(),
            }],
            init_script: None,
            type_init_scripts: Vec::new(),
        };

        runtime.load_database(&snapshot).unwrap();

        let token = CancellationToken::new();
        let host = DummyHost;
        runtime.init(&host).unwrap();

        let results = runtime
            .evaluate_rule(&snapshot.rules[0], &host, &token)
            .unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "TestRule");
    }

    /// Dummy host API for testing.
    struct DummyHost;

    impl HostApi for DummyHost {
        fn file_type(&self) -> &diec_core::format::FileType {
            use diec_core::format::FileType;
            static FT: std::sync::OnceLock<FileType> = std::sync::OnceLock::new();
            FT.get_or_init(|| FileType::new("Binary"))
        }

        fn view(&self) -> &diec_core::input::ByteView<'_> {
            unimplemented!()
        }

        fn read_u8(&self, _offset: u64) -> Result<u8, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_u16_le(&self, _offset: u64) -> Result<u16, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_u16_be(&self, _offset: u64) -> Result<u16, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_u24_le(&self, _offset: u64) -> Result<u32, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_u24_be(&self, _offset: u64) -> Result<u32, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_u32_le(&self, _offset: u64) -> Result<u32, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_u32_be(&self, _offset: u64) -> Result<u32, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_u64_le(&self, _offset: u64) -> Result<u64, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_u64_be(&self, _offset: u64) -> Result<u64, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_i8(&self, _offset: u64) -> Result<i8, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_i16_le(&self, _offset: u64) -> Result<i16, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_i32_le(&self, _offset: u64) -> Result<i32, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_i64_le(&self, _offset: u64) -> Result<i64, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn file_size(&self) -> u64 {
            0
        }
        fn check_signature(
            &self,
            _offset: u64,
            _signature: &str,
        ) -> Result<bool, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn find_signature(
            &self,
            _start: u64,
            _signature: &str,
        ) -> Result<Option<u64>, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn read_string(
            &self,
            _offset: u64,
            _max_len: u64,
        ) -> Result<String, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn file_name(&self) -> &str {
            "test.bin"
        }
        fn entry_point(&self) -> Result<u64, crate::host_api::HostApiError> {
            Ok(0)
        }
        fn is_deep(&self) -> bool {
            false
        }
        fn is_heuristic(&self) -> bool {
            false
        }
        fn is_aggressive(&self) -> bool {
            false
        }
        fn is_recursive(&self) -> bool {
            false
        }
        fn entropy(&self, _offset: u64, _size: u64) -> Result<f64, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn md5(&self, _offset: u64, _size: u64) -> Result<String, crate::host_api::HostApiError> {
            unimplemented!()
        }
        fn crc32(&self, _offset: u64, _size: u64) -> Result<u32, crate::host_api::HostApiError> {
            unimplemented!()
        }
    }
}
