#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "matching_engine.hpp"
#include "order.hpp"
#include "order_book.hpp"

namespace py = pybind11;
using namespace msnative;

PYBIND11_MODULE(_core, m) {
    m.doc() = "SynTradeX native matching engine (OrderBook + MatchingEngine only -- "
              "see ARCHITECTURE.md's Future optimization boundary and ADR-005).";

    py::class_<NativeOrder>(m, "NativeOrder")
        .def(py::init<>())
        .def_readwrite("order_id", &NativeOrder::order_id)
        .def_readwrite("side", &NativeOrder::side)
        .def_readwrite("order_type", &NativeOrder::order_type)
        .def_readwrite("quantity", &NativeOrder::quantity)
        .def_readwrite("timestamp", &NativeOrder::timestamp)
        .def_readwrite("price", &NativeOrder::price)
        .def_readwrite("filled_quantity", &NativeOrder::filled_quantity)
        .def_readwrite("seq", &NativeOrder::seq)
        .def_property_readonly("remaining_quantity", &NativeOrder::remaining_quantity)
        .def_property_readonly("is_filled", &NativeOrder::is_filled);

    py::class_<Fill>(m, "Fill")
        .def_readonly("timestamp", &Fill::timestamp)
        .def_readonly("sequence", &Fill::sequence)
        .def_readonly("trade_id", &Fill::trade_id)
        .def_readonly("price", &Fill::price)
        .def_readonly("quantity", &Fill::quantity)
        .def_readonly("buy_order_id", &Fill::buy_order_id)
        .def_readonly("sell_order_id", &Fill::sell_order_id);

    py::class_<MatchOutcome>(m, "MatchOutcome")
        .def_readonly("fills", &MatchOutcome::fills)
        .def_readonly("incoming_fill_delta", &MatchOutcome::incoming_fill_delta)
        .def_readonly("incoming_seq", &MatchOutcome::incoming_seq);

    py::class_<NativeOrderBook>(m, "NativeOrderBook")
        .def(py::init<>())
        .def("insert", &NativeOrderBook::insert)
        .def("cancel", &NativeOrderBook::cancel)
        .def("best_bid", &NativeOrderBook::best_bid)
        .def("best_ask", &NativeOrderBook::best_ask)
        .def("pop_best_bid", &NativeOrderBook::pop_best_bid)
        .def("pop_best_ask", &NativeOrderBook::pop_best_ask)
        .def("bid_depth", &NativeOrderBook::bid_depth)
        .def("ask_depth", &NativeOrderBook::ask_depth)
        .def("bid_liquidity", &NativeOrderBook::bid_liquidity)
        .def("ask_liquidity", &NativeOrderBook::ask_liquidity)
        .def("spread", &NativeOrderBook::spread)
        .def("is_empty", &NativeOrderBook::is_empty);

    py::class_<NativeMatchingEngine>(m, "NativeMatchingEngine")
        .def(py::init<>())
        .def("match", &NativeMatchingEngine::match, py::arg("incoming"), py::arg("book"),
             py::arg("timestamp"), py::arg("sequence"), py::arg("trade_id"));
}
