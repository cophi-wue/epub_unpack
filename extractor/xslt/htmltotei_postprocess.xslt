<!--  -->
<xsl:stylesheet
    version="1.0"
    xmlns="http://www.tei-c.org/ns/1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:html="http://www.w3.org/1999/xhtml"
    exclude-result-prefixes="html"
>

    <!-- Identity template: copy everything by default -->
    <xsl:template match="@* | node()">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>

    <!-- Template to match any attribute in the html namespace and not copy it -->
    <xsl:template match="@html:*" />
    <xsl:template match="@valign" />

    <!-- Find and mark paragraphs onnly containing stars => Scene Delimiters -->
    <xsl:template match="p">
        <xsl:copy>
            <!-- Copy all attributes -->
            <xsl:apply-templates select="@*"/>
            
            <!-- Conditionally add 'ana' attribute -->
            <xsl:if test="starts-with(translate(translate(translate(./text(), ' ', ''), '&#10;', ''), '&#9;', ''), '*')">
                <xsl:attribute name="ana">star-delimiter</xsl:attribute>
            </xsl:if>
            
            <!-- Copy child nodes -->
            <xsl:apply-templates select="node()"/>
        </xsl:copy>
    </xsl:template>
    

</xsl:stylesheet>
