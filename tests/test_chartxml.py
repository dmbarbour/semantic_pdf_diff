"""Charts stored as chart XML (chartxml.py; the adapters plan, "Word charts"): read from the values they cache, as
tables of categories by series or of points, each value as its number format shows it."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff.chartxml import format_number, read

NS = ('xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"')

def strings(items):
    return (f'<c:strRef><c:strCache><c:ptCount val="{len(items)}"/>' +
            "".join(f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(items)) + "</c:strCache></c:strRef>")

def numbers(items, code="General"):
    return (f'<c:numRef><c:numCache><c:formatCode>{code}</c:formatCode><c:ptCount val="{len(items)}"/>' +
            "".join(f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(items)) + "</c:numCache></c:numRef>")

def series(k, name, categories, values, code="General", x="cat", y="val"):
    return (f'<c:ser><c:idx val="{k}"/><c:order val="{k}"/><c:tx>{strings([name])}</c:tx>'
            f'<c:{x}>{categories}</c:{x}><c:{y}>{numbers(values, code)}</c:{y}></c:ser>')

def title(*runs):
    """A title of runs, as Word splits one ("Readiness for a WI", " (%)")."""
    text = "".join(f"<a:r><a:t>{run}</a:t></a:r>" for run in runs)
    return f'<c:title><c:tx><c:rich><a:bodyPr/><a:p>{text}</a:p></c:rich></c:tx></c:title>'

def axis(kind, ident, cross, position, name=""):
    return (f'<c:{kind}><c:axId val="{ident}"/><c:scaling/><c:delete val="0"/><c:axPos val="{position}"/>'
            + (title(name) if name else "") + f'<c:crossAx val="{cross}"/></c:{kind}>')

def chart(plot, head="", deleted=False):
    return (f'<c:chartSpace {NS}><c:chart>{head}<c:autoTitleDeleted val="{1 if deleted else 0}"/><c:plotArea>{plot}'
            f'</c:plotArea></c:chart></c:chartSpace>').encode()

class Formats(unittest.TestCase):
    def test_numbers_are_shown_as_their_format_shows_them(self):
        cases = [("1750", "#,##0", "1,750"), ("0.125", "0.0%", "12.5%"), ("45383", "mmm-yy", "2024-04-01"),
                 ("12.5", '0.0" ms"', "12.5 ms"), ("1234.5", '"$"#,##0.00', "$1,234.50"), ("-3.25", "0.0", "-3.3"),
                 ("0.30000000000000004", "General", "0.3"), ("475", "General", "475"), ("7", '[Red]0" kW"', "7 kW"),
                 ("12345.678", "0.00E+00", "1.23E+04"), ("n/a", "General", "n/a")]
        self.assertEqual([format_number(raw, code) for raw, code, _ in cases], [want for *_, want in cases])

class Reading(unittest.TestCase):
    def test_a_column_chart_is_categories_by_series(self):
        months = strings(["May", "June"])
        plot = ('<c:barChart><c:barDir val="col"/><c:grouping val="clustered"/>'
                + series(0, "Option 1", months, [1750, 300], "#,##0") + series(1, "Option 2", months, [225, 325], "#,##0")
                + '<c:axId val="1"/><c:axId val="2"/></c:barChart>' + axis("catAx", 1, 2, "b", "Month")
                + axis("valAx", 2, 1, "l", "MWh"))
        found = read(chart(plot, title("Readiness for a WI", " (%)")))
        self.assertEqual(found.label("Figure 1. Monthly use"),
                         "Chart: Readiness for a WI (%) (clustered column chart); categories: Month; values: MWh; "
                         "caption: Figure 1. Monthly use")
        self.assertEqual(found.tables, [(["Month", "Option 1", "Option 2"], [["May", "1,750", "225"],
                                                                             ["June", "300", "325"]])])

    def test_a_combination_a_lone_series_title_and_points(self):
        quarters = strings(["Q1", "Q2"])
        combo = ('<c:barChart><c:barDir val="bar"/><c:grouping val="stacked"/>' + series(0, "Energy", quarters, [10, 20])
                 + '<c:axId val="1"/><c:axId val="2"/></c:barChart><c:lineChart><c:grouping val="standard"/>'
                 + series(1, "Peak", quarters, [0.5, 0.75], "0%") + '<c:axId val="1"/><c:axId val="3"/></c:lineChart>')
        found = read(chart(combo))
        self.assertEqual(found.kinds, ["stacked bar chart", "line chart"])
        self.assertEqual(found.tables[0][1], [["Q1", "10", "50%"], ["Q2", "20", "75%"]])
        lone = read(chart('<c:pieChart>' + series(0, "Share of load", strings(["Fans", "Pumps"]), [60, 40])
                          + '</c:pieChart>'))
        self.assertEqual((lone.title, lone.kinds), ("Share of load", ["pie chart"]))  # as Word titles a lone series
        scatter = ('<c:scatterChart>' + series(0, "Pump P-1", numbers([100, 200]), [80.5, 61.25], x="xVal", y="yVal")
                   + '<c:axId val="1"/><c:axId val="2"/></c:scatterChart>' + axis("valAx", 1, 2, "b", "Flow (gpm)")
                   + axis("valAx", 2, 1, "l", "Head (ft)"))
        self.assertEqual(read(chart(scatter)).tables, [(["Series", "Flow (gpm)", "Head (ft)"],
                                                         [["Pump P-1", "100", "80.5"], ["Pump P-1", "200", "61.25"]])])

    def test_categories_of_several_levels_are_joined_from_the_outermost(self):
        levels = ('<c:multiLvlStrRef><c:multiLvlStrCache><c:ptCount val="3"/>'
                  '<c:lvl><c:pt idx="0"><c:v>Jan</c:v></c:pt><c:pt idx="1"><c:v>Feb</c:v></c:pt>'
                  '<c:pt idx="2"><c:v>Jan</c:v></c:pt></c:lvl>'
                  '<c:lvl><c:pt idx="0"><c:v>2025</c:v></c:pt><c:pt idx="2"><c:v>2026</c:v></c:pt></c:lvl>'
                  '</c:multiLvlStrCache></c:multiLvlStrRef>')
        found = read(chart('<c:lineChart>' + series(0, "Demand", levels, [5, 6, 7]) + '</c:lineChart>', deleted=True))
        self.assertEqual([row[0] for row in found.tables[0][1]], ["2025 > Jan", "2025 > Feb", "2026 > Jan"])
        self.assertEqual(found.title, "")  # its title deleted

if __name__ == "__main__":
    unittest.main()
