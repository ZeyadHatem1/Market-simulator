#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace msnative {

// Mirrors exchange/orderbook/order.py's Order dataclass, minus validation --
// Order.__post_init__ already validated the order in Python before it ever
// reaches this boundary (see ADR-005), so no validation is duplicated here.
struct NativeOrder {
    std::string order_id;
    int side = 0;        // 0 = BUY, 1 = SELL
    int order_type = 0;  // 0 = MARKET, 1 = LIMIT
    double quantity = 0.0;
    double timestamp = 0.0;
    std::optional<double> price;
    double filled_quantity = 0.0;
    std::optional<int64_t> seq;

    double remaining_quantity() const noexcept { return quantity - filled_quantity; }
    bool is_filled() const noexcept { return remaining_quantity() <= 1e-9; }
};

// Mirrors one TRADE_EXECUTION event's data payload.
struct Fill {
    double timestamp = 0.0;
    int64_t sequence = 0;
    std::string trade_id;
    double price = 0.0;
    double quantity = 0.0;
    std::string buy_order_id;
    std::string sell_order_id;
};

// Everything NativeMatchingEngine::match() needs to report back to the
// Python adapter, which mutates the caller's Order in place (filled_quantity,
// seq) the same way the pure-Python MatchingEngine does.
struct MatchOutcome {
    std::vector<Fill> fills;
    double incoming_fill_delta = 0.0;
    std::optional<int64_t> incoming_seq;
};

}  // namespace msnative
