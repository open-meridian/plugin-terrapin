# Troubleshooting

## Connection

| What you see | What it means | What to do |
|---|---|---|
| **No key** | No Terrapin API key is set | Enter it in Settings |
| A 401 in the last error | Terrapin refused the key | Make a new key in Terrapin's app and enter it |
| A 403 in the last error | The key's tier does not include the endpoint asked | Check your Terrapin subscription |
| Calls **rate-limited and waited out** | Terrapin answered 429; the plugin waited as Terrapin said | Nothing: it keeps under the limit Terrapin states |

## Records and terms

| What you see | What it means | What to do |
|---|---|---|
| A security with **no record**, ambiguous | Its identifiers meet two of your records | Merge them at the Instruments page |
| A curve or an index **awaits a person's acceptance** | Its record is local and its class and type are only offered | Accept them at the Instruments page; its rates are recorded at the next hourly read |
| **LEI not resolved yet** | The platform has not answered for the issuer's LEI, or its staff are reviewing it | Nothing: it is asked again at the next daily read |
| **No LEI stated** | Terrapin states no LEI for the issuer, as for most municipal issuers | The issuer field is left for a person |
| A **refusal** beside a security | Your deployment's instrument store refused part of the offer (a field of a group, say) | The rest of the offer was kept; the refusal names the field |
| A term **not offered** | Terrapin's value has no value of the template's (a 30/365 day count, an accreted-value call) | Set it at the Instruments page |

## Wants

| What you see | What it means | What to do |
|---|---|---|
| A subject declined, *not covered* | Not one of the plugin's curves or indexes, or not a municipal bond Terrapin covers | Read it from another dataset |
| Datasets: **Not licensed yet** | No deployment admin has licensed the dataset | Ask a deployment admin to license it on Data sources |
