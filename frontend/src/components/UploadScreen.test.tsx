import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import { csvFile } from "../test/fixtures";
import { UploadScreen, validateFile } from "./UploadScreen";

function setup(props: Partial<Parameters<typeof UploadScreen>[0]> = {}) {
  const onSubmit = vi.fn();
  const view = render(<UploadScreen onSubmit={onSubmit} busy={false} {...props} />);
  const input = screen.getByLabelText(/choose your csv file/i);
  return { onSubmit, input, ...view };
}

describe("validateFile", () => {
  it("accepts a normal CSV", () => {
    expect(validateFile(csvFile())).toBeNull();
    expect(validateFile(csvFile("TRADES.CSV"))).toBeNull();
  });

  it("rejects other file types, empty files and big files", () => {
    expect(validateFile(csvFile("trades.txt"))).toBe("Please choose a .csv file.");
    expect(validateFile(csvFile("trades.csv", 0))).toBe("That file is empty.");
    expect(validateFile(csvFile("trades.csv", 5 * 1024 * 1024 + 1))).toBe(
      "That file is too big. The limit is 5 MB.",
    );
  });

  it("accepts a file of exactly 5 MB", () => {
    expect(validateFile(csvFile("trades.csv", 5 * 1024 * 1024))).toBeNull();
  });
});

describe("UploadScreen", () => {
  it("explains what it does and what it does not do", () => {
    setup();

    expect(
      screen.getByRole("heading", { level: 1, name: /see the habits in your share trades/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/does not tell you what to buy or sell/i)).toBeInTheDocument();
    expect(screen.getByText(/selling shares that are up sooner/i)).toBeInTheDocument();
  });

  it("says the file is not saved", () => {
    setup();

    expect(screen.getByRole("heading", { name: /your file is not saved/i })).toBeInTheDocument();
    expect(screen.getByText(/deleted one hour after it is ready/i)).toBeInTheDocument();
  });

  it("has steps for exporting a Sharesies file", async () => {
    setup();

    await userEvent.click(screen.getByText(/how do i get my file/i));

    expect(screen.getByText(/choose transaction report/i)).toBeInTheDocument();
    expect(screen.getByText(/only sharesies files work for now/i)).toBeInTheDocument();
  });

  it("moves focus to the heading when it appears", () => {
    setup();

    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
  });

  it("keeps the button off until a good file is chosen", async () => {
    const { input, onSubmit } = setup();
    const button = screen.getByRole("button", { name: /analyse my trades/i });
    expect(button).toBeDisabled();

    await userEvent.upload(input, csvFile("my-trades.csv"));

    expect(screen.getByText("my-trades.csv")).toBeInTheDocument();
    expect(button).toBeEnabled();
    await userEvent.click(button);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0]?.[0].name).toBe("my-trades.csv");
  });

  it("shows a problem straight away and does not send a bad file", async () => {
    const { input, onSubmit } = setup();

    fireEvent.change(input, { target: { files: [csvFile("notes.txt")] } });

    expect(screen.getByRole("alert")).toHaveTextContent("Please choose a .csv file.");
    expect(screen.getByRole("button", { name: /analyse my trades/i })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("clears the problem when a good file replaces a bad one", () => {
    const { input } = setup();

    fireEvent.change(input, { target: { files: [csvFile("notes.txt")] } });
    fireEvent.change(input, { target: { files: [csvFile("trades.csv")] } });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /analyse my trades/i })).toBeEnabled();
  });

  it("takes a dropped file", () => {
    setup();
    const zone = screen.getByText(/or drop it here/i).closest(".dropzone");
    expect(zone).not.toBeNull();

    fireEvent.drop(zone as Element, { dataTransfer: { files: [csvFile("dropped.csv")] } });

    expect(screen.getByText("dropped.csv")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /analyse my trades/i })).toBeEnabled();
  });

  it("shows a problem sent back by the server", () => {
    setup({ error: "This file is not from a supported broker. Supported: sharesies" });

    expect(screen.getByRole("alert")).toHaveTextContent(/not from a supported broker/i);
  });

  it("shows a notice such as a deletion message", () => {
    setup({ notice: "Your report and trade data were deleted." });

    expect(screen.getByRole("status")).toHaveTextContent(/were deleted/i);
  });

  it("disables the button while uploading", async () => {
    const { input, rerender, onSubmit } = setup();
    await userEvent.upload(input, csvFile());

    rerender(<UploadScreen onSubmit={onSubmit} busy={true} />);

    expect(screen.getByRole("button", { name: /uploading/i })).toBeDisabled();
  });

  it("leaves out the access code field and the example link unless asked", () => {
    setup();

    expect(screen.queryByLabelText(/access code/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /example/i })).not.toBeInTheDocument();
  });

  it("needs a code before the button works, and hands it over with the file", async () => {
    sessionStorage.clear();
    const { input, onSubmit } = setup({ accessCodeRequired: true });
    await userEvent.upload(input, csvFile());
    const button = screen.getByRole("button", { name: /analyse my trades/i });
    expect(button).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/access code/i), "  open-sesame ");

    expect(button).toBeEnabled();
    await userEvent.click(button);
    expect(onSubmit.mock.calls[0]?.[1]).toBe("open-sesame");
  });

  it("hides what is typed in the access code field", () => {
    sessionStorage.clear();
    setup({ accessCodeRequired: true });

    expect(screen.getByLabelText(/access code/i)).toHaveAttribute("type", "password");
  });

  it("remembers the code for this tab only", async () => {
    sessionStorage.clear();
    const first = setup({ accessCodeRequired: true });
    await userEvent.upload(first.input, csvFile());
    await userEvent.type(screen.getByLabelText(/access code/i), "open-sesame");
    await userEvent.click(screen.getByRole("button", { name: /analyse my trades/i }));
    first.unmount();

    setup({ accessCodeRequired: true });

    expect(screen.getByLabelText(/access code/i)).toHaveValue("open-sesame");
  });

  it("offers the example report when it can show one", async () => {
    const onShowExample = vi.fn();
    setup({ onShowExample });

    await userEvent.click(screen.getByRole("button", { name: /see an example with made-up trades/i }));

    expect(onShowExample).toHaveBeenCalledTimes(1);
  });

  it("has no accessibility problems that can be found without a browser", async () => {
    const { container } = setup({ error: "A problem", notice: "A notice" });

    const results = await axe(container);

    expect(results.violations).toEqual([]);
  });
});
