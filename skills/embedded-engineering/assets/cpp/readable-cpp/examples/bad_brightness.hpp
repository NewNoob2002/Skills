// Deliberate negative example: formatting and naming only; this is valid C++.
// Do not run clang-format on this fixture: InsertBraces must be able to detect
// the single-statement bodies without braces.
namespace display_ui {
class Brightness
{
  public:
    /// @brief Set a level. Thread context only; owns no resources.
    /// @param requested_level Desired percent, clamped to 100.
    void set_level(unsigned requested_level)
    {
        if (requested_level > 100)
            requested_level = 100;
        level = requested_level;
    }

  private:
    unsigned level = 0;
};
} // namespace display_ui
