"use client";

import * as React from "react";

import { cn } from "@/utils/cn";

export type SliderTick = {
  value: number;
  label?: React.ReactNode;
};

type SliderProps = Omit<
  React.ComponentPropsWithoutRef<"div">,
  "defaultValue" | "onChange"
> & {
  defaultValue?: number[];
  disabled?: boolean;
  max?: number;
  min?: number;
  onValueChange?: (value: number[]) => void;
  onValueCommit?: (value: number[]) => void;
  step?: number;
  thumbDescriptionId?: string;
  thumbLabel?: string;
  thumbValueText?: string;
  ticks?: SliderTick[];
  value?: number[];
};

function decimalPlaces(value: number): number {
  const representation = String(value);
  const exponentIndex = representation.toLowerCase().indexOf("e-");
  if (exponentIndex >= 0) {
    return Number(representation.slice(exponentIndex + 2));
  }
  return representation.includes(".")
    ? representation.length - representation.indexOf(".") - 1
    : 0;
}

export function snapSliderValue(
  rawValue: number,
  min: number,
  max: number,
  step: number,
): number {
  const bounded = Math.min(max, Math.max(min, rawValue));
  const stepIndex = Math.round((bounded - min) / step);
  const snapped = min + stepIndex * step;
  return Number(
    Math.min(max, Math.max(min, snapped)).toFixed(decimalPlaces(step)),
  );
}

export function sliderValueFromClientX(
  clientX: number,
  trackLeft: number,
  trackWidth: number,
  min: number,
  max: number,
  step: number,
): number {
  if (trackWidth <= 0) return min;
  const ratio = Math.min(1, Math.max(0, (clientX - trackLeft) / trackWidth));
  return snapSliderValue(min + ratio * (max - min), min, max, step);
}

function Slider({
  "aria-label": ariaLabel,
  className,
  defaultValue,
  disabled = false,
  max = 100,
  min = 0,
  onKeyDown,
  onPointerCancel,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onValueChange,
  onValueCommit,
  step = 1,
  thumbDescriptionId,
  thumbLabel,
  thumbValueText,
  ticks,
  value,
  ...props
}: SliderProps) {
  const trackRef = React.useRef<HTMLDivElement>(null);
  const activePointerId = React.useRef<number | null>(null);
  const [uncontrolledValue, setUncontrolledValue] = React.useState(
    () => defaultValue?.[0] ?? min,
  );
  const isControlled = value !== undefined;
  const currentValue = snapSliderValue(
    value?.[0] ?? uncontrolledValue,
    min,
    max,
    step,
  );
  const currentValueRef = React.useRef(currentValue);
  currentValueRef.current = currentValue;

  const emitValue = React.useCallback(
    (nextValue: number) => {
      const snapped = snapSliderValue(nextValue, min, max, step);
      currentValueRef.current = snapped;
      if (!isControlled) setUncontrolledValue(snapped);
      onValueChange?.([snapped]);
    },
    [isControlled, max, min, onValueChange, step],
  );

  const updateFromPointer = React.useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track) return;
      const bounds = track.getBoundingClientRect();
      emitValue(
        sliderValueFromClientX(
          clientX,
          bounds.left,
          bounds.width,
          min,
          max,
          step,
        ),
      );
    },
    [emitValue, max, min, step],
  );

  const tickItems = React.useMemo<SliderTick[]>(() => {
    if (ticks) return ticks;
    const count = Math.floor((max - min) / step) + 1;
    if (count > 21) {
      return [
        { value: min, label: min },
        { value: max, label: max },
      ];
    }
    return Array.from({ length: Math.max(1, count) }, (_, index) => {
      const tickValue = snapSliderValue(min + index * step, min, max, step);
      return { value: tickValue, label: tickValue };
    });
  }, [max, min, step, ticks]);

  const valuePercent =
    max === min ? 0 : ((currentValue - min) / (max - min)) * 100;

  return (
    <div
      {...props}
      data-disabled={disabled || undefined}
      data-slot="slider"
      role="slider"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled || undefined}
      aria-describedby={thumbDescriptionId}
      aria-label={thumbLabel ?? ariaLabel}
      aria-orientation="horizontal"
      aria-valuemax={max}
      aria-valuemin={min}
      aria-valuenow={currentValue}
      aria-valuetext={thumbValueText}
      className={cn(
        "relative w-full min-w-0 touch-none select-none rounded-md px-3 pb-3 pt-9 outline-none",
        "focus-visible:ring-2 focus-visible:ring-ring/45 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "data-[disabled=true]:cursor-not-allowed data-[disabled=true]:opacity-50",
        className,
      )}
      onKeyDown={(event) => {
        onKeyDown?.(event);
        if (event.defaultPrevented || disabled) return;

        let nextValue: number | null = null;
        if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
          nextValue = currentValueRef.current - step;
        } else if (event.key === "ArrowRight" || event.key === "ArrowUp") {
          nextValue = currentValueRef.current + step;
        } else if (event.key === "Home") {
          nextValue = min;
        } else if (event.key === "End") {
          nextValue = max;
        }
        if (nextValue === null) return;

        event.preventDefault();
        emitValue(nextValue);
        onValueCommit?.([snapSliderValue(nextValue, min, max, step)]);
      }}
      onPointerDown={(event) => {
        onPointerDown?.(event);
        if (
          event.defaultPrevented ||
          disabled ||
          activePointerId.current !== null ||
          (event.pointerType === "mouse" && event.button !== 0)
        ) {
          return;
        }
        activePointerId.current = event.pointerId;
        event.currentTarget.focus();
        event.currentTarget.setPointerCapture?.(event.pointerId);
        updateFromPointer(event.clientX);
      }}
      onPointerMove={(event) => {
        onPointerMove?.(event);
        if (disabled || activePointerId.current !== event.pointerId) return;
        updateFromPointer(event.clientX);
      }}
      onPointerUp={(event) => {
        onPointerUp?.(event);
        if (activePointerId.current !== event.pointerId) return;
        updateFromPointer(event.clientX);
        activePointerId.current = null;
        event.currentTarget.releasePointerCapture?.(event.pointerId);
        onValueCommit?.([currentValueRef.current]);
      }}
      onPointerCancel={(event) => {
        onPointerCancel?.(event);
        if (activePointerId.current !== event.pointerId) return;
        activePointerId.current = null;
        event.currentTarget.releasePointerCapture?.(event.pointerId);
        onValueCommit?.([currentValueRef.current]);
      }}
      onLostPointerCapture={(event) => {
        if (activePointerId.current === event.pointerId) {
          activePointerId.current = null;
        }
      }}
    >
      <div aria-hidden="true" className="absolute inset-x-3 top-1 h-6">
        {tickItems.map((tick) => {
          const tickPercent =
            max === min ? 0 : ((tick.value - min) / (max - min)) * 100;
          return (
            <span
              key={tick.value}
              data-slot="slider-tick-label"
              className={cn(
                "absolute -translate-x-1/2 font-mono text-[11px] font-semibold tabular-nums text-muted-foreground",
                tick.value === currentValue && "text-foreground",
              )}
              style={{ left: `${tickPercent}%` }}
            >
              {tick.label ?? tick.value}
            </span>
          );
        })}
      </div>
      <div
        ref={trackRef}
        data-slot="slider-track"
        aria-hidden="true"
        className="relative h-2 w-full rounded-full border border-border bg-background"
      >
        <span
          data-slot="slider-range"
          className="absolute inset-y-0 left-0 rounded-full bg-burgundy/20"
          style={{ width: `${valuePercent}%` }}
        />
        {tickItems.map((tick) => {
          const tickPercent =
            max === min ? 0 : ((tick.value - min) / (max - min)) * 100;
          return (
            <span
              key={tick.value}
              data-slot="slider-tick"
              className="absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-border bg-surface"
              style={{ left: `${tickPercent}%` }}
            />
          );
        })}
        <span
          data-slot="slider-thumb"
          className={cn(
            "absolute top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-burgundy bg-surface",
            "shadow-[0_1px_3px_rgba(24,24,27,0.16)] transition-transform active:scale-95",
          )}
          style={{ left: `${valuePercent}%` }}
        />
      </div>
    </div>
  );
}

export { Slider };
