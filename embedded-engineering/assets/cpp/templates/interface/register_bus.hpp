/// @file register_bus.hpp
/// @brief “寄存器总线”契约：器件驱动依赖它，而不是 HAL。
///
/// 构建期绑定（每块板固定一种总线）用模板参数 + 本 Concept，零间接调用；
/// C++17 下用 is_register_bus_v 在驱动内 static_assert。

#ifndef PROJ_REGISTER_BUS_HPP
#define PROJ_REGISTER_BUS_HPP

#include <cstdint>
#include <type_traits>
#include <utility>

#include "etl/span.h"
#include "proj_status.hpp"

namespace proj
{

/// C++17 回退：检查 Status Bus::read(std::uint8_t, etl::span<std::uint8_t>)
/// 与 Status Bus::write(std::uint8_t, etl::span<const std::uint8_t>)。
template <class Bus, class = void> struct IsRegisterBus : std::false_type
{
};

template <class Bus>
struct IsRegisterBus<
    Bus, std::void_t<decltype(std::declval<Bus &>().read(std::uint8_t{},
                                                         std::declval<etl::span<std::uint8_t>>())),
                     decltype(std::declval<Bus &>().write(
                         std::uint8_t{}, std::declval<etl::span<const std::uint8_t>>()))>>
    : std::bool_constant<
          std::is_same_v<decltype(std::declval<Bus &>().read(
                             std::uint8_t{}, std::declval<etl::span<std::uint8_t>>())),
                         Status> &&
          std::is_same_v<decltype(std::declval<Bus &>().write(
                             std::uint8_t{}, std::declval<etl::span<const std::uint8_t>>())),
                         Status>>
{
};

template <class Bus> inline constexpr bool kIsRegisterBus = IsRegisterBus<Bus>::value;

#if defined(__cpp_concepts) && (__cpp_concepts >= 201907L)
template <class Bus>
concept RegisterBus = kIsRegisterBus<Bus>;
#define PROJ_REGISTER_BUS ::proj::RegisterBus
#else
#define PROJ_REGISTER_BUS class
#endif

} // namespace proj

#endif // PROJ_REGISTER_BUS_HPP
