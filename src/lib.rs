// const VERSION: &'static str = env!("CARGO_PKG_VERSION");
#[pyo3::pymodule]
#[pyo3(name = "nonebot_adapter_walleq")]
fn pyadapter(_py: pyo3::Python<'_>, m: &pyo3::prelude::PyModule) -> pyo3::PyResult<()> {
    m.add_class::<WalleQ>()?;
    Ok(())
}

use std::sync::Arc;

use pyo3::types::PyBytes;
use pyo3::{PyAny, PyResult, Python};
use tokio::sync::broadcast::{channel, Sender as BTx};
use walle_core::OneBot;
use walle_q::config::QQConfig;
use walle_q::database::WQDatabase;
use walle_q::init;
use walle_q::multi::MultiAH;

#[pyo3::pyclass]
pub struct WalleQ {
    ob: Arc<OneBot<MultiAH, PyoHandler>>,
    action_tx: BTx<Vec<u8>>,
    event_tx: BTx<Vec<u8>>,
}

#[pyo3::pymethods]
impl WalleQ {
    #[new]
    fn new() -> Self {
        let (action_tx, _) = channel(64);
        let (event_tx, _) = channel(64);
        Self {
            ob: Arc::new(OneBot::new(
                MultiAH::new(None, 10, Arc::new(WQDatabase::default())), //todo
                PyoHandler {
                    action_tx: action_tx.clone(),
                    event_tx: event_tx.clone(),
                },
            )),
            action_tx,
            event_tx,
        }
    }

    fn run<'a>(&self, config: Vec<u8>, py: Python<'a>) -> PyResult<&'a PyAny> {
        let config: std::collections::HashMap<String, QQConfig> =
            rmp_serde::from_slice(&config).unwrap();
        let ob = self.ob.clone();
        let mut event_rx = self.event_tx.subscribe();
        pyo3_asyncio::tokio::future_into_py(py, async move {
            init().await;
            ob.start(config, (), true).await.unwrap(); //todo()
            while let Ok(data) = event_rx.recv().await {
                let f = Python::with_gil(|py| {
                    pyo3_asyncio::tokio::into_future(
                        py.import("nonebot_adapter_walleq")
                            .unwrap()
                            .call_method1("_call_data", (PyBytes::new(py, &data),))
                            .unwrap(),
                    )
                })
                .unwrap();
                f.await.unwrap();
            }
            Ok(Python::with_gil(|py| py.None()))
        })
    }

    fn call_api(&self, action: Vec<u8>) -> PyResult<()> {
        self.action_tx.send(action).unwrap(); //todo
        Ok(())
    }
}

use walle_core::prelude::{async_trait, Action, Event};
use walle_core::util::Echo;
use walle_core::{ActionHandler, EventHandler, WalleResult};

pub struct PyoHandler {
    pub action_tx: BTx<Vec<u8>>,
    pub event_tx: BTx<Vec<u8>>,
}

#[async_trait]
impl EventHandler for PyoHandler {
    type Config = ();
    async fn start<AH, EH>(
        &self,
        ob: &Arc<OneBot<AH, EH>>,
        _config: Self::Config,
    ) -> WalleResult<Vec<tokio::task::JoinHandle<()>>>
    where
        AH: ActionHandler + Send + Sync + 'static,
        EH: EventHandler + Send + Sync + 'static,
    {
        let ob = ob.clone();
        let mut action_rx = self.action_tx.subscribe();
        let event_tx = self.event_tx.clone();
        Ok(vec![tokio::spawn(async move {
            while let Ok(data) = action_rx.recv().await {
                let (action, echos) = rmp_serde::from_slice::<Echo<Action>>(&data)
                    .unwrap()
                    .unpack();
                let resp = ob.handle_action(action).await.unwrap(); //todo
                event_tx
                    .send(rmp_serde::to_vec(&echos.pack(resp)).unwrap())
                    .unwrap(); //todo
            }
        })])
    }
    async fn call<AH, EH>(&self, event: Event, _: &Arc<OneBot<AH, EH>>) -> WalleResult<()>
    where
        AH: ActionHandler + Send + Sync + 'static,
        EH: EventHandler + Send + Sync + 'static,
    {
        self.event_tx
            .send(rmp_serde::to_vec(&event).unwrap())
            .unwrap(); //todo
        Ok(())
    }
}
