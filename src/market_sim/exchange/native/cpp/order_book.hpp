#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <unordered_set>
#include <vector>

#include "order.hpp"

namespace msnative {

// Mirrors exchange/orderbook/order_book.py exactly: two binary heaps
// (highest-price-first for bids, lowest-price-first for asks, tied broken by
// lowest seq = earliest arrival = time priority), lazy-delete cancellation
// via a cancelled-id set rather than removing entries in place.
class NativeOrderBook {
public:
    int64_t insert(NativeOrder order);
    void cancel(const std::string& order_id);

    // Peeking mutates: cancelled entries sitting at the heap top are
    // permanently discarded, same as the Python `_clean` step -- these are
    // not const for that reason, matching the Python OrderBook's actual
    // (also side-effecting) best_bid()/best_ask().
    std::optional<NativeOrder> best_bid();
    std::optional<NativeOrder> best_ask();
    std::optional<NativeOrder> pop_best_bid();
    std::optional<NativeOrder> pop_best_ask();

    int bid_depth() const;
    int ask_depth() const;
    double bid_liquidity() const;
    double ask_liquidity() const;
    std::optional<double> spread();
    bool is_empty() const;

private:
    using Comparator = bool (*)(const NativeOrder&, const NativeOrder&);

    void clean(std::vector<NativeOrder>& heap, Comparator worse);

    std::vector<NativeOrder> bids_;
    std::vector<NativeOrder> asks_;
    std::unordered_set<std::string> cancelled_;
    int64_t seq_counter_ = 0;
};

}  // namespace msnative
