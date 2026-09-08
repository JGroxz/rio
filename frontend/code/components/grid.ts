import {
    componentsById,
    ComponentStatesUpdateContext,
} from "../componentManagement";
import { ComponentId } from "../dataModels";
import { range, zip } from "../utils";
import {
    ComponentBase,
    ComponentState,
    DeltaState,
    getMaxOuterSize,
} from "./componentBase";

type GridChildPosition = {
    row: number;
    column: number;
    width: number;
    height: number;
};

export type GridState = ComponentState & {
    _type_: "Grid-builtin";
    _children: ComponentId[];
    _child_positions: GridChildPosition[];
    row_spacing: number;
    column_spacing: number;
};

export class GridComponent extends ComponentBase<GridState> {
    createElement(context: ComponentStatesUpdateContext): HTMLElement {
        let element = document.createElement("div");
        element.classList.add("rio-grid");
        return element;
    }

    updateElement(
        deltaState: DeltaState<GridState>,
        context: ComponentStatesUpdateContext
    ): void {
        super.updateElement(deltaState, context);

        if (deltaState._children !== undefined) {
            let childPositions =
                deltaState._child_positions ?? this.state._child_positions;

            this.replaceChildren(
                context,
                deltaState._children,
                this.element,
                true
            );

            for (let [childWrapper, childPos] of zip(
                this.element.children,
                childPositions
            )) {
                // Note: `rio.Grid` starts counting at row/column 0, but CSS
                // starts counting at 1
                let style = (childWrapper as HTMLElement).style;
                style.gridColumn = `${childPos.column + 1} / ${
                    childPos.column + 1 + childPos.width
                }`;
                style.gridRow = `${childPos.row + 1} / ${
                    childPos.row + 1 + childPos.height
                }`;
            }

            this.updateTrackSizes(deltaState._children, childPositions);
        }

        if (deltaState.row_spacing !== undefined) {
            this.element.style.rowGap = `${deltaState.row_spacing}rem`;
        }

        if (deltaState.column_spacing !== undefined) {
            this.element.style.columnGap = `${deltaState.column_spacing}rem`;
        }
    }

    onChildLayoutChanged(): void {
        this.updateTrackSizes(
            this.state._children,
            this.state._child_positions
        );
    }

    updateTrackSizes(
        childIds: ComponentId[],
        childPositions: GridChildPosition[]
    ): void {
        let childrenWithPositions: [ComponentBase, GridChildPosition][] =
            childIds.map((childId: ComponentId, index: number) => [
                componentsById[childId]!,
                childPositions[index],
            ]);

        // Sort the children by the number of rows they take up
        let childrenByNumberOfRows = Array.from(childrenWithPositions);
        childrenByNumberOfRows.sort((a, b) => a[1].height - b[1].height);

        let nRows = 0;
        let growingRows = new Set();

        for (let [childComponent, childPosition] of childrenByNumberOfRows) {
            // Keep track of how how many rows this grid has
            nRows = Math.max(nRows, childPosition.row + childPosition.height);

            let allRows = range(
                childPosition.row,
                childPosition.row + childPosition.height
            );

            // Determine which rows need to grow
            if (!childComponent.state._grow_[1]) {
                continue;
            }

            // Does any of the rows already grow?
            let alreadyGrowing = allRows.some((row) => growingRows.has(row));

            // If not, mark them all as growing
            if (!alreadyGrowing) {
                for (let row of allRows) {
                    growingRows.add(row);
                }
            }
        }

        // Sort the children by the number of columns they take up
        let childrenByNumberOfColumns = Array.from(childrenWithPositions);
        childrenByNumberOfColumns.sort((a, b) => a[1].width - b[1].width);

        let nColumns = 0;
        let growingColumns = new Set();

        for (let [childComponent, childPosition] of childrenByNumberOfColumns) {
            // Keep track of how how many columns this grid has
            nColumns = Math.max(
                nColumns,
                childPosition.column + childPosition.width
            );

            let allColumns = range(
                childPosition.column,
                childPosition.column + childPosition.width
            );

            // Determine which columns need to grow
            if (!childComponent.state._grow_[0]) {
                continue;
            }

            // Does any of the rows already grow?
            let alreadyGrowing = allColumns.some((column) =>
                growingColumns.has(column)
            );

            // If not, mark them all as growing
            if (!alreadyGrowing) {
                for (let column of allColumns) {
                    growingColumns.add(column);
                }
            }
        }

        const NO_GROW = "min-content";

        // A growing track stops once every child in it has reached its
        // maximum. `minmax(auto, cap)` grows up to the cap and hands the rest
        // to the other `auto` tracks; the `auto` minimum keeps the natural
        // size as the floor.
        let grow = (cap: number | null) =>
            cap === null ? "auto" : `minmax(auto, ${cap}rem)`;

        let columnCaps = trackCaps(childrenWithPositions, 0, nColumns);
        let rowCaps = trackCaps(childrenWithPositions, 1, nRows);

        let columnWidths: string[] = [];
        for (let i = 0; i < nColumns; i++) {
            // If nobody wants to grow, all of them do
            let grows = growingColumns.size === 0 || growingColumns.has(i);
            columnWidths.push(grows ? grow(columnCaps[i]) : NO_GROW);
        }

        let rowHeights: string[] = [];
        for (let i = 0; i < nRows; i++) {
            let grows = growingRows.size === 0 || growingRows.has(i);
            rowHeights.push(grows ? grow(rowCaps[i]) : NO_GROW);
        }

        this.element.style.gridTemplateColumns = columnWidths.join(" ");
        this.element.style.gridTemplateRows = rowHeights.join(" ");
    }
}

/// Per track, the largest maximum outer size among the children placed in it,
/// or `null` if the track can't be capped: some child there has no maximum,
/// or spans several tracks (CSS can't cap the sum of tracks).
function trackCaps(
    children: [ComponentBase, GridChildPosition][],
    axis: 0 | 1,
    nTracks: number
): (number | null)[] {
    let caps: (number | null)[] = new Array(nTracks).fill(null);
    let uncappable: boolean[] = new Array(nTracks).fill(false);

    for (let [childComponent, childPosition] of children) {
        let start = axis === 0 ? childPosition.column : childPosition.row;
        let span = axis === 0 ? childPosition.width : childPosition.height;
        let cap = getMaxOuterSize(childComponent, axis);

        for (let track of range(start, start + span)) {
            if (cap === null || span !== 1) {
                uncappable[track] = true;
            } else {
                caps[track] = Math.max(caps[track] ?? 0, cap);
            }
        }
    }

    return caps.map((cap, track) => (uncappable[track] ? null : cap));
}
