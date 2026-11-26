import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

describe("Vue test environment", () => {
  it("mounts a component into the DOM", () => {
    const component = defineComponent({
      render: () => h("button", { type: "button" }, "ready"),
    });

    const wrapper = mount(component);

    expect(wrapper.get("button").text()).toBe("ready");
  });
});
