Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

[xml]$xaml = @'
<Window
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="Claude Code"
    Width="370" Height="200"
    WindowStartupLocation="CenterScreen"
    Topmost="True"
    WindowStyle="None"
    AllowsTransparency="True"
    Background="Transparent"
    ResizeMode="NoResize"
    ShowInTaskbar="False">
    <Window.Resources>
        <Storyboard x:Key="FadeIn">
            <DoubleAnimation
                Storyboard.TargetName="MainBorder"
                Storyboard.TargetProperty="Opacity"
                From="0" To="1" Duration="0:0:0.3">
                <DoubleAnimation.EasingFunction>
                    <CubicEase EasingMode="EaseOut"/>
                </DoubleAnimation.EasingFunction>
            </DoubleAnimation>
            <DoubleAnimation
                Storyboard.TargetName="ScaleXform"
                Storyboard.TargetProperty="ScaleX"
                From="0.85" To="1" Duration="0:0:0.3">
                <DoubleAnimation.EasingFunction>
                    <CubicEase EasingMode="EaseOut"/>
                </DoubleAnimation.EasingFunction>
            </DoubleAnimation>
            <DoubleAnimation
                Storyboard.TargetName="ScaleXform"
                Storyboard.TargetProperty="ScaleY"
                From="0.85" To="1" Duration="0:0:0.3">
                <DoubleAnimation.EasingFunction>
                    <CubicEase EasingMode="EaseOut"/>
                </DoubleAnimation.EasingFunction>
            </DoubleAnimation>
        </Storyboard>
    </Window.Resources>
    <Border x:Name="MainBorder" CornerRadius="18" Margin="16" Opacity="0"
            RenderTransformOrigin="0.5,0.5">
        <Border.RenderTransform>
            <ScaleTransform x:Name="ScaleXform" ScaleX="1" ScaleY="1"/>
        </Border.RenderTransform>
        <Border.Effect>
            <DropShadowEffect BlurRadius="20" ShadowDepth="3" Opacity="0.25" Color="#8B5CF6"/>
        </Border.Effect>
        <Border.Background>
            <LinearGradientBrush StartPoint="0,0" EndPoint="1,1">
                <GradientStop Color="#FFF0F7FF" Offset="0"/>
                <GradientStop Color="#FFFFF0FB" Offset="0.5"/>
                <GradientStop Color="#FFF5F0FF" Offset="1"/>
            </LinearGradientBrush>
        </Border.Background>
        <Grid>
            <Grid.RowDefinitions>
                <RowDefinition Height="*"/>
                <RowDefinition Height="Auto"/>
            </Grid.RowDefinitions>
            <StackPanel Grid.Row="0" VerticalAlignment="Center" HorizontalAlignment="Center" Margin="24,20,24,8">
                <TextBlock Text="&#x2728;" FontSize="32" HorizontalAlignment="Center" Margin="0,0,0,8"/>
                <TextBlock Text="Claude is done!" FontSize="16" FontWeight="SemiBold"
                           HorizontalAlignment="Center" Foreground="#6D28D9"
                           FontFamily="Segoe UI"/>
            </StackPanel>
            <Button x:Name="OkButton" Grid.Row="1" Content="OK" Width="100" Height="34"
                    Margin="0,0,0,20" HorizontalAlignment="Center" Cursor="Hand"
                    FontSize="14" FontWeight="SemiBold" Foreground="White"
                    FontFamily="Yu Gothic UI, Meiryo UI, Segoe UI"
                    BorderThickness="0">
                <Button.Template>
                    <ControlTemplate TargetType="Button">
                        <Border x:Name="BtnBorder" CornerRadius="17" Padding="0"
                                Background="#A78BFA">
                            <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
                        </Border>
                        <ControlTemplate.Triggers>
                            <Trigger Property="IsMouseOver" Value="True">
                                <Setter TargetName="BtnBorder" Property="Background" Value="#8B5CF6"/>
                            </Trigger>
                            <Trigger Property="IsPressed" Value="True">
                                <Setter TargetName="BtnBorder" Property="Background" Value="#7C3AED"/>
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Button.Template>
            </Button>
        </Grid>
    </Border>
</Window>
'@

$reader = New-Object System.Xml.XmlNodeReader $xaml
$window = [System.Windows.Markup.XamlReader]::Load($reader)

$okButton = $window.FindName("OkButton")
$okButton.Add_Click({ $window.Close() })

$window.Add_Loaded({
    $sb = $window.FindResource("FadeIn")
    $sb.Begin($window)
})

$window.Add_MouseLeftButtonDown({ $window.DragMove() })

$window.ShowDialog() | Out-Null
