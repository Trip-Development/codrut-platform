import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Slider, sliderValueFromClientX } from "./slider";

class PointerEventMock extends MouseEvent {
  pointerId: number;
  pointerType: string;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
    this.pointerType = init.pointerType ?? "";
  }
}

Object.defineProperty(window, "PointerEvent", {
  configurable: true,
  value: PointerEventMock,
});

function ControlledSlider({
  disabled = false,
  onCommit,
}: {
  disabled?: boolean;
  onCommit?: (value: number[]) => void;
}) {
  const [value, setValue] = useState([5]);
  return (
    <Slider
      aria-label="Nivel"
      min={0}
      max={10}
      step={1}
      value={value}
      disabled={disabled}
      onValueChange={setValue}
      onValueCommit={onCommit}
      ticks={Array.from({ length: 11 }, (_, value) => ({
        value,
        label: value,
      }))}
    />
  );
}

function mockTrackBounds(slider: HTMLElement, width: number) {
  const track = slider.querySelector<HTMLElement>("[data-slot='slider-track']");
  if (!track) throw new Error("Slider track was not rendered.");
  vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
    bottom: 40,
    height: 8,
    left: 20,
    right: 20 + width,
    top: 32,
    width,
    x: 20,
    y: 32,
    toJSON: () => ({}),
  });
}

describe("Slider", () => {
  afterEach(() => {
    cleanup();
  });

  it("uses the same snapping geometry at desktop and mobile widths", () => {
    expect(sliderValueFromClientX(260, 20, 320, 0, 10, 1)).toBe(8);
    expect(sliderValueFromClientX(140, 20, 160, 0, 10, 1)).toBe(8);
    expect(sliderValueFromClientX(-40, 20, 160, 0, 10, 1)).toBe(0);
    expect(sliderValueFromClientX(400, 20, 160, 0, 10, 1)).toBe(10);
  });

  it("renders numbers above an outlined track and snaps clicks", () => {
    render(<ControlledSlider />);
    const slider = screen.getByRole("slider", { name: "Nivel" });
    mockTrackBounds(slider, 100);

    expect(slider.querySelector("[data-slot='slider-track']")?.className).toContain(
      "border",
    );
    expect(
      slider.querySelector("[data-slot='slider-tick-label']")?.parentElement
        ?.className,
    ).toContain("top-1");
    expect(slider.querySelectorAll("[data-slot='slider-tick']")).toHaveLength(11);

    fireEvent.pointerDown(slider, {
      pointerId: 1,
      pointerType: "mouse",
      button: 0,
      clientX: 95,
    });
    fireEvent.pointerUp(slider, {
      pointerId: 1,
      pointerType: "mouse",
      button: 0,
      clientX: 95,
    });

    expect(slider.getAttribute("aria-valuenow")).toBe("8");
  });

  it("supports dragging and stops tracking after pointer cancellation", () => {
    const onCommit = vi.fn();
    render(<ControlledSlider onCommit={onCommit} />);
    const slider = screen.getByRole("slider", { name: "Nivel" });
    mockTrackBounds(slider, 100);

    fireEvent.pointerDown(slider, {
      pointerId: 4,
      pointerType: "touch",
      clientX: 40,
    });
    fireEvent.pointerMove(slider, {
      pointerId: 4,
      pointerType: "touch",
      clientX: 100,
    });
    expect(slider.getAttribute("aria-valuenow")).toBe("8");

    fireEvent.pointerCancel(slider, {
      pointerId: 4,
      pointerType: "touch",
    });
    fireEvent.pointerMove(slider, {
      pointerId: 4,
      pointerType: "touch",
      clientX: 30,
    });

    expect(slider.getAttribute("aria-valuenow")).toBe("8");
    expect(onCommit).toHaveBeenLastCalledWith([8]);
  });

  it("supports arrows and Home/End for a controlled value", () => {
    render(<ControlledSlider />);
    const slider = screen.getByRole("slider", { name: "Nivel" });

    slider.focus();
    fireEvent.keyDown(slider, { key: "ArrowUp" });
    expect(slider.getAttribute("aria-valuenow")).toBe("6");
    fireEvent.keyDown(slider, { key: "ArrowLeft" });
    expect(slider.getAttribute("aria-valuenow")).toBe("5");
    fireEvent.keyDown(slider, { key: "End" });
    expect(slider.getAttribute("aria-valuenow")).toBe("10");
    fireEvent.keyDown(slider, { key: "Home" });
    expect(slider.getAttribute("aria-valuenow")).toBe("0");
  });

  it("removes disabled sliders from the tab order and ignores input", () => {
    render(<ControlledSlider disabled />);
    const slider = screen.getByRole("slider", { name: "Nivel" });
    mockTrackBounds(slider, 100);

    fireEvent.keyDown(slider, { key: "End" });
    fireEvent.pointerDown(slider, {
      pointerId: 1,
      pointerType: "mouse",
      button: 0,
      clientX: 120,
    });

    expect(slider.getAttribute("aria-valuenow")).toBe("5");
    expect(slider.getAttribute("aria-disabled")).toBe("true");
    expect(slider.getAttribute("tabindex")).toBe("-1");
  });
});
