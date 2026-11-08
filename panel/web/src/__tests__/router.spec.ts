import { describe, expect, it } from "vitest";

import router from "../router";

describe("router", () => {
  it("loads page views lazily", () => {
    for (const name of ["overview", "config", "runs", "logs", "settings", "login", "setup"]) {
      const route = router.getRoutes().find((item) => item.name === name);
      expect(route, `missing route: ${name}`).toBeTruthy();
      const component = route?.components?.default;
      expect(typeof component, `route ${name} should be lazy`).toBe("function");
    }
  });
});
