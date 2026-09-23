# Validation

Thirteen automated tests passed on Python with PyMuPDF 1.26.6 and Pydantic 2.13.5.

The end-to-end test creates temporary PDFs, sends native text and rendered images to a local HTTP stub, generates HTML/JSON, and reruns with zero additional HTTP calls because of caching. Other tests cover retrieval across modalities, many-to-one candidates, unit conversions, uncertainty gates, byte budgets, malformed/truncated responses, call limits, visual refinement, quote rejection and escaped report content.

The bundled demo is hand-authored synthetic evidence with fixture judgments. It is not a VLM accuracy evaluation. No live external model was called. Before deployment, measure extraction recall, candidate retrieval recall and difference precision on domain-specific labeled examples, especially dense charts, table continuations and diagram topology.

Environment configuration tests verify typed parsing, API-key exclusion from serialized settings, empty-variable fallback, invalid-value handling and CLI > file > environment precedence.
