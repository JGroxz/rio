import pytest

import rio
from rio.testing import BrowserClient
from tests.utils.layouting import verify_layout


async def test_max_width_is_centered_in_full_size_parent() -> None:
    """
    `Rectangle` passes on all of its space. The child stops at its maximum and,
    lacking an alignment, is centered in the leftover.
    """
    layouter = await verify_layout(
        lambda: rio.Rectangle(
            content=rio.Text("hi", key="text", max_width=10),
        )
    )

    layout = layouter.get_layout_by_key("text")

    assert layout.allocated_inner_width == pytest.approx(10, abs=0.2)
    assert layout.allocated_outer_width > 10
    assert layout.left_in_viewport_inner == pytest.approx(
        layout.left_in_viewport_outer + (layout.allocated_outer_width - 10) / 2,
        abs=0.2,
    )


async def test_max_width_respects_explicit_alignment() -> None:
    """
    An aligned component only takes up its natural size, clamped to the
    maximum, and the alignment decides where it goes.
    """
    layouter = await verify_layout(
        lambda: rio.Rectangle(
            content=rio.Text(
                "hi",
                key="text",
                min_width=20,
                max_width=10,
                align_x=0,
            ),
        )
    )

    layout = layouter.get_layout_by_key("text")

    # min wins over max, so the clamp lands on 20
    assert layout.allocated_inner_width == pytest.approx(20, abs=0.2)
    assert layout.left_in_viewport_inner == pytest.approx(
        layout.left_in_viewport_outer, abs=0.2
    )


LONG_LINE = "This text is a lot wider than eight font heights, and won't wrap"


async def test_max_never_goes_below_natural_width() -> None:
    """
    Components are never smaller than their natural size. A maximum below it
    has no effect, and the sibling is placed after the natural width.
    """
    layouter = await verify_layout(
        lambda: rio.Row(
            rio.Text(LONG_LINE, key="text", max_width=8),
            rio.Text("sibling", key="sibling"),
            key="row",
        )
    )

    row = layouter.get_layout_by_key("row")
    text = layouter.get_layout_by_key("text")
    sibling = layouter.get_layout_by_key("sibling")

    assert text.natural_width > 8
    assert text.allocated_inner_width == pytest.approx(
        text.natural_width, abs=0.2
    )
    assert sibling.left_in_viewport_outer == pytest.approx(
        row.left_in_viewport_inner + text.natural_width, abs=0.2
    )


async def test_max_never_goes_below_natural_width_when_aligned() -> None:
    layouter = await verify_layout(
        lambda: rio.Rectangle(
            content=rio.Text(LONG_LINE, key="text", max_width=8, align_x=1),
        )
    )

    layout = layouter.get_layout_by_key("text")

    assert layout.allocated_inner_width == pytest.approx(
        layout.natural_width, abs=0.2
    )
    assert layout.left_in_viewport_inner + layout.allocated_inner_width == (
        pytest.approx(
            layout.left_in_viewport_outer + layout.allocated_outer_width,
            abs=0.2,
        )
    )


async def test_max_never_goes_below_natural_height() -> None:
    layouter = await verify_layout(
        lambda: rio.Row(
            rio.Column(
                *[rio.Text(f"line {i}") for i in range(6)],
                key="column",
                max_height=1,
            ),
            key="row",
        )
    )

    column = layouter.get_layout_by_key("column")

    assert column.natural_height > 1
    assert column.allocated_inner_height == pytest.approx(
        column.natural_height, abs=0.2
    )


async def test_max_only_axis_uses_no_transform() -> None:
    """
    A transformed ancestor becomes the containing block of `position: fixed`
    descendants. The maximum-only path must not introduce one.
    """
    async with BrowserClient(
        lambda: rio.Rectangle(content=rio.Text("hi", max_width=10))
    ) as client:
        result = await client.execute_js(
            """
            (() => {
                const inner = document.querySelector(".rio-align-inner");
                const probe = document.createElement("div");
                probe.style.cssText = "position:fixed;left:0;top:0;width:1px;height:1px";
                inner.appendChild(probe);
                const rect = probe.getBoundingClientRect();
                probe.remove();
                return {
                    transform: getComputedStyle(inner).transform,
                    fixedLeft: rect.left,
                    innerLeft: inner.getBoundingClientRect().left,
                };
            })()
            """
        )

    assert result["transform"] == "none"
    assert result["innerLeft"] > 0  # it really is centered
    assert result["fixedLeft"] == 0  # and fixed children still see the viewport


async def test_aligned_component_below_max_keeps_natural_size() -> None:
    layouter = await verify_layout(
        lambda: rio.Rectangle(
            content=rio.Text("hi", key="text", max_width=10, align_x=0),
        )
    )

    layout = layouter.get_layout_by_key("text")

    assert layout.allocated_inner_width == pytest.approx(
        layout.natural_width, abs=0.2
    )
    assert layout.allocated_inner_width < 10


async def test_max_height_is_centered_in_full_size_parent() -> None:
    layouter = await verify_layout(
        lambda: rio.Rectangle(
            content=rio.Text("hi", key="text", max_height=5),
        )
    )

    layout = layouter.get_layout_by_key("text")

    assert layout.allocated_inner_height == pytest.approx(5, abs=0.2)
    assert layout.top_in_viewport_inner == pytest.approx(
        layout.top_in_viewport_outer + (layout.allocated_outer_height - 5) / 2,
        abs=0.2,
    )


async def test_max_below_min_is_ignored() -> None:
    """
    A maximum below the minimum is contradictory. The minimum wins.
    """
    layouter = await verify_layout(
        lambda: rio.Rectangle(
            content=rio.Text("hi", key="text", min_width=20, max_width=10),
        )
    )

    layout = layouter.get_layout_by_key("text")

    assert layout.allocated_inner_width == pytest.approx(20, abs=0.2)


@pytest.mark.parametrize("horizontal", [True, False])
async def test_capped_grower_yields_to_sibling(horizontal: bool) -> None:
    """
    Two growers, one of them capped. The capped one stops at its maximum and
    the sibling receives everything else.
    """
    if horizontal:
        container_type = rio.Row
        capped_kwargs = dict(grow_x=True, max_width=10)
        grower_kwargs = dict(grow_x=True)
    else:
        container_type = rio.Column
        capped_kwargs = dict(grow_y=True, max_height=10)
        grower_kwargs = dict(grow_y=True)

    layouter = await verify_layout(
        lambda: container_type(
            rio.Text("capped", key="capped", **capped_kwargs),
            rio.Text("grower", key="grower", **grower_kwargs),
            key="container",
        )
    )

    axis = "width" if horizontal else "height"
    container = layouter.get_layout_by_key("container")
    capped = layouter.get_layout_by_key("capped")
    grower = layouter.get_layout_by_key("grower")

    container_size = getattr(container, f"allocated_inner_{axis}")
    assert container_size > 10

    assert getattr(capped, f"allocated_outer_{axis}") == pytest.approx(
        10, abs=0.2
    )
    assert getattr(grower, f"allocated_outer_{axis}") == pytest.approx(
        container_size - 10, abs=0.2
    )


async def test_max_size_includes_margin_in_linear_container() -> None:
    """
    The wrapper handed out by the `Row` caps at the maximum *plus* margins, so
    the component itself still gets its full maximum.
    """
    layouter = await verify_layout(
        lambda: rio.Row(
            rio.Text(
                "capped",
                key="capped",
                grow_x=True,
                max_width=10,
                margin_x=1,
            ),
            rio.Text("grower", key="grower", grow_x=True),
            key="row",
        )
    )

    row = layouter.get_layout_by_key("row")
    capped = layouter.get_layout_by_key("capped")
    grower = layouter.get_layout_by_key("grower")

    assert capped.allocated_outer_width == pytest.approx(12, abs=0.2)
    assert capped.allocated_inner_width == pytest.approx(10, abs=0.2)
    assert grower.allocated_outer_width == pytest.approx(
        row.allocated_inner_width - 12, abs=0.2
    )


async def test_all_children_capped_leaves_space_at_end() -> None:
    """
    Without growers every child grows. If all of them are capped, nobody can
    use the leftover and it stays at the end, like in a flexbox.
    """
    layouter = await verify_layout(
        lambda: rio.Row(
            rio.Text("a", key="a", max_width=10),
            rio.Text("b", key="b", max_width=20),
            key="row",
        )
    )

    row = layouter.get_layout_by_key("row")
    a = layouter.get_layout_by_key("a")
    b = layouter.get_layout_by_key("b")

    assert a.allocated_outer_width == pytest.approx(10, abs=0.2)
    assert a.left_in_viewport_outer == pytest.approx(
        row.left_in_viewport_inner, abs=0.2
    )
    assert b.allocated_outer_width == pytest.approx(20, abs=0.2)
    assert b.left_in_viewport_outer == pytest.approx(
        row.left_in_viewport_inner + 10, abs=0.2
    )


async def test_max_size_on_minor_axis_is_centered() -> None:
    """
    A `Row` hands the full height to its children. A capped child stops at
    its maximum and is centered vertically.
    """
    layouter = await verify_layout(
        lambda: rio.Row(
            rio.Text("hi", key="text", max_height=3),
            key="row",
        )
    )

    row = layouter.get_layout_by_key("row")
    text = layouter.get_layout_by_key("text")

    assert row.allocated_inner_height > 3
    assert text.allocated_inner_height == pytest.approx(3, abs=0.2)
    assert text.top_in_viewport_inner == pytest.approx(
        row.top_in_viewport_inner + (row.allocated_inner_height - 3) / 2,
        abs=0.2,
    )


async def test_grid_capped_column_yields_to_sibling_column() -> None:
    """
    A growing column whose only child is capped stops at the cap. The other
    growing column receives the rest.
    """

    def build() -> rio.Component:
        grid = rio.Grid(key="grid")
        grid.add(
            rio.Text("capped", key="capped", max_width=10, grow_x=True),
            row=0,
            column=0,
        )
        grid.add(rio.Text("grower", key="grower", grow_x=True), row=0, column=1)
        return grid

    layouter = await verify_layout(build)

    grid = layouter.get_layout_by_key("grid")
    capped = layouter.get_layout_by_key("capped")
    grower = layouter.get_layout_by_key("grower")

    assert capped.allocated_outer_width == pytest.approx(10, abs=0.2)
    assert grower.allocated_outer_width == pytest.approx(
        grid.allocated_inner_width - 10, abs=0.2
    )


async def test_grid_spanning_child_keeps_its_columns_uncapped() -> None:
    def build() -> rio.Component:
        grid = rio.Grid(key="grid")
        grid.add(
            rio.Text("wide", key="wide", max_width=10, grow_x=True),
            row=0,
            column=0,
            width=2,
        )
        grid.add(rio.Text("a", key="a", grow_x=True), row=1, column=0)
        grid.add(rio.Text("b", key="b", grow_x=True), row=1, column=1)
        return grid

    layouter = await verify_layout(build)

    grid = layouter.get_layout_by_key("grid")
    wide = layouter.get_layout_by_key("wide")

    # Two columns can't be capped as a sum, so they keep growing; the child
    # is centered inside the full width instead
    assert wide.allocated_outer_width == pytest.approx(
        grid.allocated_inner_width, abs=0.2
    )
    assert wide.allocated_inner_width == pytest.approx(10, abs=0.2)
