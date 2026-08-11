from market_sim.core.engine.runtime_engine import RuntimeEngine
from market_sim.core.models import EventType
from market_sim.exchange.execution import TradeLog
from market_sim.exchange.gateway import ExchangeGateway
from market_sim.market.microstructure import SlippageModel

from .adapter import NativeMatchingEngine, NativeOrderBook


def build_native_exchange(
    runtime: RuntimeEngine, slippage_model: SlippageModel | None = None
) -> tuple[NativeOrderBook, TradeLog, ExchangeGateway]:
    """
    Opt-in, native-engine counterpart to exchange.gateway.build_exchange().
    build_exchange() itself is untouched and stays the default -- this is a
    separate entry point, not a replacement (see ADR-005). Reuses
    ExchangeGateway unmodified: it's already duck-typed on book/
    matching_engine, so no changes were needed there either.

    Raises ImportError (from NativeOrderBook/NativeMatchingEngine's own
    constructors) if the compiled extension hasn't been built -- check
    market_sim.exchange.native.NATIVE_AVAILABLE first if that matters to
    the caller.
    """
    book = NativeOrderBook()
    trade_log = TradeLog()
    gateway = ExchangeGateway(
        book=book,
        matching_engine=NativeMatchingEngine(slippage_model=slippage_model),
        queue=runtime.queue,
        clock=runtime.clock,
        runtime=runtime,
    )
    gateway.register(runtime.loop)
    runtime.loop.register_handler(EventType.TRADE_EXECUTION, trade_log.record)

    return book, trade_log, gateway
