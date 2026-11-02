# Pages

Both pages are the data role's, the same on every data plugin, under
**Manage**, for the plugin's admins. Neither shows a rate, a price or a
yield. Each is also a read tool on the deployment's MCP, answering what the
page shows.

## Connection (`read_connection`)

- **Key:** the mode (Live, Sample data or No key), whether the key is set,
  how many securities are listed; and **Securities**, how many resolved to
  a record. Its `…` opens each security: Terrapin's description, the record
  it resolved to (or why none), its issuer's company record (or why none),
  and how many terms were offered, with the store's refusal where it
  refused one; and **Prices**: not recorded, and why.
- **Limits and use:** the limit Terrapin's policy states (25 a minute until
  it says), the calls made and those rate-limited and waited out, the last
  error.
- **Stream:** it does not stream.

## Datasets (`read_datasets`)

- Anything Terrapin stated that was not recorded, with how often (a point that is no tenor, a term with no
  value of the template's, a print with no amount).
- **Served:** its three datasets as the catalogue lists them, whether each is
  licensed, what it recorded and declined, and each curve's and index's
  record.
- **Wants:** the wants it answered and keeps current; **Subjects**.
