#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "order.hpp"
#include "order_book.hpp"

namespace msnative {

// Mirrors exchange/matching/matching_engine.py exactly, minus slippage:
// slippage stays Python-only (see ADR-005) -- this engine always fills at
// the resting order's exact price, i.e. the equivalent of
// MatchingEngine(slippage_model=None). The Python adapter applies slippage
// to the returned fills afterward when a model is configured.
class NativeMatchingEngine {
public:
    MatchOutcome match(NativeOrder incoming, NativeOrderBook& book, double timestamp,
                        int64_t sequence, const std::string& trade_id);

private:
    void match_limit(NativeOrder& incoming, NativeOrderBook& book, double timestamp,
                      int64_t sequence, const std::string& trade_id, std::vector<Fill>& fills);
    void match_market(NativeOrder& incoming, NativeOrderBook& book, double timestamp,
                       int64_t sequence, const std::string& trade_id, std::vector<Fill>& fills);
    Fill execute(NativeOrder& incoming, NativeOrder& resting, double timestamp, int64_t sequence,
                 const std::string& trade_id, int fill_count);
};

}  // namespace msnative
