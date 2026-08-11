#include "order_book.hpp"

#include <algorithm>

namespace msnative {

namespace {

// std::push_heap/pop_heap treat front() as the "maximum" per the comparator,
// so "worse" here means "should be popped later" -- the best order (highest
// bid price / lowest ask price, ties broken by earliest seq) sorts as the
// heap's maximum and ends up at front().
bool bid_worse(const NativeOrder& a, const NativeOrder& b) {
    if (a.price.value() != b.price.value()) {
        return a.price.value() < b.price.value();
    }
    return a.seq.value() > b.seq.value();
}

bool ask_worse(const NativeOrder& a, const NativeOrder& b) {
    if (a.price.value() != b.price.value()) {
        return a.price.value() > b.price.value();
    }
    return a.seq.value() > b.seq.value();
}

}  // namespace

int64_t NativeOrderBook::insert(NativeOrder order) {
    // Preserve original time priority if this order is being re-queued after
    // a partial fill; otherwise assign a fresh sequence number.
    if (!order.seq.has_value()) {
        order.seq = seq_counter_++;
    }

    if (order.side == 0) {
        bids_.push_back(order);
        std::push_heap(bids_.begin(), bids_.end(), bid_worse);
    } else {
        asks_.push_back(order);
        std::push_heap(asks_.begin(), asks_.end(), ask_worse);
    }
    return *order.seq;
}

void NativeOrderBook::cancel(const std::string& order_id) { cancelled_.insert(order_id); }

void NativeOrderBook::clean(std::vector<NativeOrder>& heap, Comparator worse) {
    while (!heap.empty() && cancelled_.find(heap.front().order_id) != cancelled_.end()) {
        std::pop_heap(heap.begin(), heap.end(), worse);
        heap.pop_back();
    }
}

std::optional<NativeOrder> NativeOrderBook::best_bid() {
    clean(bids_, bid_worse);
    if (bids_.empty()) return std::nullopt;
    return bids_.front();
}

std::optional<NativeOrder> NativeOrderBook::best_ask() {
    clean(asks_, ask_worse);
    if (asks_.empty()) return std::nullopt;
    return asks_.front();
}

std::optional<NativeOrder> NativeOrderBook::pop_best_bid() {
    while (!bids_.empty()) {
        std::pop_heap(bids_.begin(), bids_.end(), bid_worse);
        NativeOrder order = bids_.back();
        bids_.pop_back();
        if (cancelled_.find(order.order_id) == cancelled_.end()) {
            return order;
        }
    }
    return std::nullopt;
}

std::optional<NativeOrder> NativeOrderBook::pop_best_ask() {
    while (!asks_.empty()) {
        std::pop_heap(asks_.begin(), asks_.end(), ask_worse);
        NativeOrder order = asks_.back();
        asks_.pop_back();
        if (cancelled_.find(order.order_id) == cancelled_.end()) {
            return order;
        }
    }
    return std::nullopt;
}

int NativeOrderBook::bid_depth() const {
    int count = 0;
    for (const auto& order : bids_) {
        if (cancelled_.find(order.order_id) == cancelled_.end()) count++;
    }
    return count;
}

int NativeOrderBook::ask_depth() const {
    int count = 0;
    for (const auto& order : asks_) {
        if (cancelled_.find(order.order_id) == cancelled_.end()) count++;
    }
    return count;
}

double NativeOrderBook::bid_liquidity() const {
    double total = 0.0;
    for (const auto& order : bids_) {
        if (cancelled_.find(order.order_id) == cancelled_.end()) total += order.remaining_quantity();
    }
    return total;
}

double NativeOrderBook::ask_liquidity() const {
    double total = 0.0;
    for (const auto& order : asks_) {
        if (cancelled_.find(order.order_id) == cancelled_.end()) total += order.remaining_quantity();
    }
    return total;
}

std::optional<double> NativeOrderBook::spread() {
    auto bb = best_bid();
    auto ba = best_ask();
    if (!bb.has_value() || !ba.has_value()) return std::nullopt;
    return ba->price.value() - bb->price.value();
}

bool NativeOrderBook::is_empty() const { return bid_depth() == 0 && ask_depth() == 0; }

}  // namespace msnative
