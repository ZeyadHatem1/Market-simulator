#include "matching_engine.hpp"

#include <algorithm>

namespace msnative {

MatchOutcome NativeMatchingEngine::match(NativeOrder incoming, NativeOrderBook& book,
                                          double timestamp, int64_t sequence,
                                          const std::string& trade_id) {
    double initial_filled = incoming.filled_quantity;
    std::vector<Fill> fills;

    if (incoming.order_type == 1) {
        match_limit(incoming, book, timestamp, sequence, trade_id, fills);
    } else {
        match_market(incoming, book, timestamp, sequence, trade_id, fills);
    }

    MatchOutcome outcome;
    outcome.fills = std::move(fills);
    outcome.incoming_fill_delta = incoming.filled_quantity - initial_filled;
    outcome.incoming_seq = incoming.seq;
    return outcome;
}

void NativeMatchingEngine::match_limit(NativeOrder& incoming, NativeOrderBook& book,
                                        double timestamp, int64_t sequence,
                                        const std::string& trade_id, std::vector<Fill>& fills) {
    int fill_count = 0;

    while (!incoming.is_filled()) {
        std::optional<NativeOrder> resting_opt;

        if (incoming.side == 0) {
            auto best = book.best_ask();
            if (!best.has_value() || incoming.price.value() < best->price.value()) break;
            resting_opt = book.pop_best_ask();
        } else {
            auto best = book.best_bid();
            if (!best.has_value() || incoming.price.value() > best->price.value()) break;
            resting_opt = book.pop_best_bid();
        }

        NativeOrder resting = *resting_opt;
        fills.push_back(execute(incoming, resting, timestamp, sequence, trade_id, fill_count));
        fill_count++;

        if (!resting.is_filled()) {
            book.insert(resting);  // re-queued, seq preserved -> keeps time priority
        }
    }

    if (!incoming.is_filled()) {
        incoming.seq = book.insert(incoming);
    }
}

void NativeMatchingEngine::match_market(NativeOrder& incoming, NativeOrderBook& book,
                                         double timestamp, int64_t sequence,
                                         const std::string& trade_id, std::vector<Fill>& fills) {
    int fill_count = 0;

    while (!incoming.is_filled()) {
        std::optional<NativeOrder> resting_opt =
            (incoming.side == 0) ? book.pop_best_ask() : book.pop_best_bid();
        if (!resting_opt.has_value()) break;

        NativeOrder resting = *resting_opt;
        fills.push_back(execute(incoming, resting, timestamp, sequence, trade_id, fill_count));
        fill_count++;

        if (!resting.is_filled()) {
            book.insert(resting);
        }
    }
    // no re-insert of incoming -- market orders never rest
}

Fill NativeMatchingEngine::execute(NativeOrder& incoming, NativeOrder& resting, double timestamp,
                                    int64_t sequence, const std::string& trade_id,
                                    int fill_count) {
    double fill_qty = std::min(incoming.remaining_quantity(), resting.remaining_quantity());
    double fill_price = resting.price.value();

    incoming.filled_quantity += fill_qty;
    resting.filled_quantity += fill_qty;

    bool incoming_is_buy = incoming.side == 0;
    std::string buy_id = incoming_is_buy ? incoming.order_id : resting.order_id;
    std::string sell_id = incoming_is_buy ? resting.order_id : incoming.order_id;

    Fill fill;
    fill.timestamp = timestamp;
    fill.sequence = sequence + fill_count;
    fill.trade_id = trade_id + "-" + std::to_string(fill_count);
    fill.price = fill_price;
    fill.quantity = fill_qty;
    fill.buy_order_id = buy_id;
    fill.sell_order_id = sell_id;
    return fill;
}

}  // namespace msnative
