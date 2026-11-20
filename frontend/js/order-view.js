// builds the DOM for one order (#97). used by the checkout confirmation on
// restaurant.html and by orders.html so an order looks the same in both

import { money, placedAt } from "./orders.js";

function addFact(list, label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  list.append(term, description);
}

function cell(tag, text, scope) {
  const element = document.createElement(tag);
  element.textContent = text;
  if (scope) element.scope = scope;
  return element;
}

export function orderDetails(order, restaurantName = null) {
  const wrapper = document.createElement("div");
  wrapper.className = "order";

  const facts = document.createElement("dl");
  const address = order.delivery_address;
  addFact(facts, "Order", `#${order.order_id}`);
  addFact(facts, "Placed", placedAt(order.created_at));
  addFact(facts, "Restaurant", restaurantName ?? `Restaurant #${order.restaurant_id}`);
  addFact(facts, "Status", order.status.charAt(0).toUpperCase() + order.status.slice(1));
  addFact(facts, "Deliver to",
    `${address.address}, ${address.city}, ${address.province} ${address.postal_code}`);

  // the table can scroll sideways on its own so the page never does
  const scroller = document.createElement("div");
  scroller.className = "table-scroll";
  const table = document.createElement("table");
  table.append(cell("caption", "Items"));

  const head = document.createElement("thead");
  const headings = document.createElement("tr");
  for (const label of ["Item", "Price", "Qty", "Line total"]) headings.append(cell("th", label, "col"));
  head.append(headings);

  const body = document.createElement("tbody");
  for (const item of order.items) {
    const row = document.createElement("tr");
    row.append(
      cell("th", item.name, "row"),
      cell("td", money(item.unit_price)),
      cell("td", String(item.quantity)),
      cell("td", money(item.line_total)),
    );
    body.append(row);
  }

  // subtotal and total are the ones the backend saved, never added up here
  const foot = document.createElement("tfoot");
  for (const [label, amount] of [["Subtotal", order.subtotal], ["Total", order.total]]) {
    const row = document.createElement("tr");
    const name = cell("th", label, "row");
    name.colSpan = 3;
    row.append(name, cell("td", money(amount)));
    foot.append(row);
  }

  table.append(head, body, foot);
  scroller.append(table);
  wrapper.append(facts, scroller);
  return wrapper;
}
